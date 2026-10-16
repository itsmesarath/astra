# Exact accepted C7 primitive extent transfer; no executable driver.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$intakeInvariant = [Globalization.CultureInfo]::InvariantCulture
$intakeUtf8 = [Text.UTF8Encoding]::new($false, $true)
$intakeU64Max = [Numerics.BigInteger]::Parse('18446744073709551615', $intakeInvariant)
$intakeI64Min = [Numerics.BigInteger]::Parse('-9223372036854775808', $intakeInvariant)

function Stop-IntakePrimitive {
    param([string]$Reason)
    $intakeFailure = [IO.InvalidDataException]::new('local-intake-primitive:' + $Reason)
    $intakeFailure.Data['local_intake_reason'] = $Reason
    throw $intakeFailure
}

function Get-IntakeSha {
    param([byte[]]$Bytes)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
}

function Convert-IntakeClock {
    param([object]$Ticks, [object]$Frequency)
    if (($Ticks -isnot [long] -and $Ticks -isnot [int]) -or
        ($Frequency -isnot [long] -and $Frequency -isnot [int]) -or
        $Ticks -lt 0 -or $Frequency -le 0) {
        Stop-IntakePrimitive 'clock'
    }
    $intakeQuotient = [Numerics.BigInteger]::Divide(
        ([Numerics.BigInteger]$Ticks * [Numerics.BigInteger]1000000000),
        [Numerics.BigInteger]$Frequency
    )
    if ($intakeQuotient -lt 0 -or $intakeQuotient -gt $intakeU64Max) {
        Stop-IntakePrimitive 'clock'
    }
    return [ulong]$intakeQuotient
}

function Get-IntakeUtcNs {
    $intakeUtcTicks = [Numerics.BigInteger][DateTime]::UtcNow.Ticks
    $intakeEpochTicks = [Numerics.BigInteger][DateTime]::UnixEpoch.Ticks
    $intakeUtcNs = ($intakeUtcTicks - $intakeEpochTicks) * [Numerics.BigInteger]100
    if ($intakeUtcNs -lt 0 -or $intakeUtcNs -gt $intakeU64Max) { Stop-IntakePrimitive 'clock' }
    return [ulong]$intakeUtcNs
}

function Skip-IntakeWhitespace {
    param([hashtable]$State)
    while ($State.Offset -lt $State.Text.Length -and
        [int]$State.Text[$State.Offset] -in @(32, 9, 10, 13)) {
        $State.Offset++
    }
}

function Read-IntakeString {
    param([hashtable]$State)
    if ($State.Offset -ge $State.Text.Length -or $State.Text[$State.Offset] -cne '"') {
        Stop-IntakePrimitive 'json'
    }
    $State.Offset++
    $intakeString = [Text.StringBuilder]::new()
    while ($State.Offset -lt $State.Text.Length) {
        $intakeStop = $State.Text.IndexOfAny([char[]]@('"', '\'), $State.Offset)
        if ($intakeStop -lt 0) { Stop-IntakePrimitive 'json' }
        $intakeSegment = $State.Text.Substring($State.Offset, $intakeStop - $State.Offset)
        if ([regex]::IsMatch($intakeSegment, '[\x00-\x1f]')) { Stop-IntakePrimitive 'json' }
        $null = $intakeString.Append($intakeSegment)
        $State.Offset = $intakeStop + 1
        if ($State.Text[$intakeStop] -ceq '"') { return $intakeString.ToString() }
        if ($State.Offset -ge $State.Text.Length) { Stop-IntakePrimitive 'json' }
        $intakeEscape = $State.Text[$State.Offset]
        $State.Offset++
        switch -CaseSensitive ($intakeEscape) {
            '"' { $null = $intakeString.Append('"') }
            '\' { $null = $intakeString.Append('\') }
            '/' { $null = $intakeString.Append('/') }
            'b' { $null = $intakeString.Append([char]8) }
            'f' { $null = $intakeString.Append([char]12) }
            'n' { $null = $intakeString.Append([char]10) }
            'r' { $null = $intakeString.Append([char]13) }
            't' { $null = $intakeString.Append([char]9) }
            'u' {
                if ($State.Offset + 4 -gt $State.Text.Length) { Stop-IntakePrimitive 'json' }
                $intakeHex = $State.Text.Substring($State.Offset, 4)
                if ($intakeHex -cnotmatch '\A[0-9a-fA-F]{4}\z') { Stop-IntakePrimitive 'json' }
                $null = $intakeString.Append([char][Convert]::ToInt32($intakeHex, 16))
                $State.Offset += 4
            }
            default { Stop-IntakePrimitive 'json' }
        }
    }
    Stop-IntakePrimitive 'json'
}

function Read-IntakeValue {
    param([hashtable]$State, [int]$Depth)
    Skip-IntakeWhitespace $State
    if ($State.Offset -ge $State.Text.Length) { Stop-IntakePrimitive 'json' }
    $intakeToken = $State.Text[$State.Offset]
    if ($intakeToken -ceq '"') { return Read-IntakeString $State }
    if ($intakeToken -ceq '[') {
        if ($Depth -ge 64) { Stop-IntakePrimitive 'json' }
        $State.Offset++
        $intakeValues = [Collections.Generic.List[object]]::new()
        Skip-IntakeWhitespace $State
        if ($State.Offset -lt $State.Text.Length -and $State.Text[$State.Offset] -ceq ']') {
            $State.Offset++
            return ,([object[]]$intakeValues.ToArray())
        }
        while ($true) {
            $intakeValue = Read-IntakeValue $State ($Depth + 1)
            $intakeValues.Add($intakeValue)
            Skip-IntakeWhitespace $State
            if ($State.Offset -ge $State.Text.Length) { Stop-IntakePrimitive 'json' }
            $intakeSeparator = $State.Text[$State.Offset]
            $State.Offset++
            if ($intakeSeparator -ceq ']') { return ,([object[]]$intakeValues.ToArray()) }
            if ($intakeSeparator -cne ',') { Stop-IntakePrimitive 'json' }
        }
    }
    if ($intakeToken -ceq '{') {
        if ($Depth -ge 64) { Stop-IntakePrimitive 'json' }
        $State.Offset++
        $intakeObject = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
        Skip-IntakeWhitespace $State
        if ($State.Offset -lt $State.Text.Length -and $State.Text[$State.Offset] -ceq '}') {
            $State.Offset++
            return ,$intakeObject
        }
        while ($true) {
            Skip-IntakeWhitespace $State
            $intakeKey = Read-IntakeString $State
            if ($intakeObject.ContainsKey($intakeKey)) { Stop-IntakePrimitive 'duplicate' }
            Skip-IntakeWhitespace $State
            if ($State.Offset -ge $State.Text.Length -or $State.Text[$State.Offset] -cne ':') {
                Stop-IntakePrimitive 'json'
            }
            $State.Offset++
            $intakeValue = Read-IntakeValue $State ($Depth + 1)
            $intakeObject.Add($intakeKey, $intakeValue)
            Skip-IntakeWhitespace $State
            if ($State.Offset -ge $State.Text.Length) { Stop-IntakePrimitive 'json' }
            $intakeSeparator = $State.Text[$State.Offset]
            $State.Offset++
            if ($intakeSeparator -ceq '}') { return ,$intakeObject }
            if ($intakeSeparator -cne ',') { Stop-IntakePrimitive 'json' }
        }
    }
    foreach ($intakeLiteral in @('null', 'true', 'false')) {
        if ($State.Text.Length - $State.Offset -ge $intakeLiteral.Length -and
            $State.Text.Substring($State.Offset, $intakeLiteral.Length) -ceq $intakeLiteral) {
            $State.Offset += $intakeLiteral.Length
            if ($intakeLiteral -ceq 'null') { return $null }
            return ($intakeLiteral -ceq 'true')
        }
    }
    $intakeNumberPattern = [regex]::new('\G-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
    $intakeNumber = $intakeNumberPattern.Match($State.Text, $State.Offset)
    if (-not $intakeNumber.Success -or $intakeNumber.Index -ne $State.Offset) {
        Stop-IntakePrimitive 'json'
    }
    $State.Offset += $intakeNumber.Length
    if ($intakeNumber.Value.IndexOfAny([char[]]@('.', 'e', 'E')) -ge 0) {
        Stop-IntakePrimitive 'number'
    }
    $intakeInteger = [Numerics.BigInteger]::Parse($intakeNumber.Value, $intakeInvariant)
    if ($intakeInteger -lt $intakeI64Min -or $intakeInteger -gt $intakeU64Max) {
        Stop-IntakePrimitive 'number'
    }
    return $intakeInteger
}

function Read-IntakeJson {
    param([byte[]]$Bytes)
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 239 -and $Bytes[1] -eq 187 -and $Bytes[2] -eq 191) {
        Stop-IntakePrimitive 'encoding'
    }
    try { $intakeText = $intakeUtf8.GetString($Bytes) }
    catch {
        if ($_.Exception -is [Text.DecoderFallbackException] -or
            $_.Exception.InnerException -is [Text.DecoderFallbackException]) {
            Stop-IntakePrimitive 'encoding'
        }
        throw
    }
    $intakeState = @{ Text = $intakeText; Offset = 0 }
    $intakeParsed = Read-IntakeValue $intakeState 0
    Skip-IntakeWhitespace $intakeState
    if ($intakeState.Offset -ne $intakeState.Text.Length) { Stop-IntakePrimitive 'json' }
    return ,$intakeParsed
}

function Convert-IntakeQuoted {
    param([string]$Text)
    if (-not [regex]::IsMatch($Text, '["\\\x00-\x1f\x7f-\uffff]')) { return '"' + $Text + '"' }
    $intakeQuoted = [Text.StringBuilder]::new()
    $null = $intakeQuoted.Append('"')
    foreach ($intakeChar in $Text.ToCharArray()) {
        $intakeCode = [int]$intakeChar
        switch ($intakeCode) {
            34 { $null = $intakeQuoted.Append('\"') }
            92 { $null = $intakeQuoted.Append('\\') }
            8 { $null = $intakeQuoted.Append('\b') }
            12 { $null = $intakeQuoted.Append('\f') }
            10 { $null = $intakeQuoted.Append('\n') }
            13 { $null = $intakeQuoted.Append('\r') }
            9 { $null = $intakeQuoted.Append('\t') }
            default {
                if ($intakeCode -lt 32 -or $intakeCode -ge 127) {
                    $null = $intakeQuoted.Append('\u' + $intakeCode.ToString('x4', $intakeInvariant))
                }
                else { $null = $intakeQuoted.Append($intakeChar) }
            }
        }
    }
    $null = $intakeQuoted.Append('"')
    return $intakeQuoted.ToString()
}

function Compare-IntakeScalarKeys {
    param([string]$Left, [string]$Right)
    $intakeLeftIndex = 0
    $intakeRightIndex = 0
    while ($intakeLeftIndex -lt $Left.Length -and $intakeRightIndex -lt $Right.Length) {
        $intakeLeftCode = [int]$Left[$intakeLeftIndex++]
        $intakeRightCode = [int]$Right[$intakeRightIndex++]
        if ($intakeLeftCode -ge 55296 -and $intakeLeftCode -le 56319 -and
            $intakeLeftIndex -lt $Left.Length -and
            [int]$Left[$intakeLeftIndex] -ge 56320 -and [int]$Left[$intakeLeftIndex] -le 57343) {
            $intakeLeftCode = 65536 + (($intakeLeftCode - 55296) * 1024) + ([int]$Left[$intakeLeftIndex++] - 56320)
        }
        if ($intakeRightCode -ge 55296 -and $intakeRightCode -le 56319 -and
            $intakeRightIndex -lt $Right.Length -and
            [int]$Right[$intakeRightIndex] -ge 56320 -and [int]$Right[$intakeRightIndex] -le 57343) {
            $intakeRightCode = 65536 + (($intakeRightCode - 55296) * 1024) + ([int]$Right[$intakeRightIndex++] - 56320)
        }
        if ($intakeLeftCode -lt $intakeRightCode) { return -1 }
        if ($intakeLeftCode -gt $intakeRightCode) { return 1 }
    }
    if ($intakeLeftIndex -lt $Left.Length) { return 1 }
    if ($intakeRightIndex -lt $Right.Length) { return -1 }
    return 0
}

function Convert-IntakeCanonicalText {
    param([AllowNull()][object]$Value, [int]$Depth = 0)
    if ($null -eq $Value) { return 'null' }
    if ($Value -is [bool]) { if ($Value) { return 'true' }; return 'false' }
    if ($Value -is [string]) { return Convert-IntakeQuoted $Value }
    if ($Value -is [Numerics.BigInteger] -or $Value -is [long] -or $Value -is [int] -or
        $Value -is [ulong] -or $Value -is [uint]) {
        $intakeNumber = [Numerics.BigInteger]$Value
        if ($intakeNumber -lt $intakeI64Min -or $intakeNumber -gt $intakeU64Max) { Stop-IntakePrimitive 'number' }
        return $intakeNumber.ToString('D', $intakeInvariant)
    }
    if ($Depth -ge 64) { Stop-IntakePrimitive 'json' }
    if ($Value -is [Collections.IDictionary]) {
        [string[]]$intakeKeys = @($Value.Keys)
        for ($intakeIndex = 1; $intakeIndex -lt $intakeKeys.Length; $intakeIndex++) {
            $intakeMoving = $intakeKeys[$intakeIndex]
            $intakeBefore = $intakeIndex - 1
            while ($intakeBefore -ge 0 -and (Compare-IntakeScalarKeys $intakeKeys[$intakeBefore] $intakeMoving) -gt 0) {
                $intakeKeys[$intakeBefore + 1] = $intakeKeys[$intakeBefore]
                $intakeBefore--
            }
            $intakeKeys[$intakeBefore + 1] = $intakeMoving
        }
        $intakeMembers = [Collections.Generic.List[string]]::new()
        foreach ($intakeKey in $intakeKeys) {
            $intakeMembers.Add((Convert-IntakeQuoted $intakeKey) + ':' + (Convert-IntakeCanonicalText $Value[$intakeKey] ($Depth + 1)))
        }
        return '{' + [string]::Join(',', $intakeMembers) + '}'
    }
    if ($Value -is [object[]] -or $Value -is [Collections.Generic.List[object]]) {
        $intakeElements = [Collections.Generic.List[string]]::new()
        foreach ($intakeElement in $Value) { $intakeElements.Add((Convert-IntakeCanonicalText $intakeElement ($Depth + 1))) }
        return '[' + [string]::Join(',', $intakeElements) + ']'
    }
    Stop-IntakePrimitive 'json'
}

function Convert-IntakeCanonicalBytes {
    param([AllowNull()][object]$Value)
    return ,$intakeUtf8.GetBytes((Convert-IntakeCanonicalText $Value))
}

function Assert-IntakeKeys {
    param([object]$Value, [string[]]$Keys)
    if ($Value -isnot [Collections.IDictionary] -or $Value.Count -ne $Keys.Count) {
        Stop-IntakePrimitive 'schema'
    }
    foreach ($intakeKey in $Keys) { if (@($Value.Keys) -cnotcontains $intakeKey) { Stop-IntakePrimitive 'schema' } }
}

function Get-IntakeLiteralBytes {
    param([object]$Value)
    Assert-IntakeKeys $Value @('encoding', 'data')
    if ($Value['encoding'] -isnot [string] -or $Value['data'] -isnot [string]) {
        Stop-IntakePrimitive 'schema'
    }
    if ($Value['encoding'] -ceq 'ascii') {
        foreach ($intakeChar in $Value['data'].ToCharArray()) { if ([int]$intakeChar -gt 127) { Stop-IntakePrimitive 'schema' } }
        $intakeBytes = $intakeUtf8.GetBytes($Value['data'])
    }
    elseif ($Value['encoding'] -ceq 'hex' -and $Value['data'] -cmatch '\A(?:[0-9a-f]{2})*\z') {
        $intakeBytes = [Convert]::FromHexString($Value['data'])
    }
    else { Stop-IntakePrimitive 'schema' }
    if ($intakeBytes.Length -gt 8192) { Stop-IntakePrimitive 'schema' }
    return ,$intakeBytes
}

function Get-IntakeExpectedReason {
    param([Management.Automation.ErrorRecord]$Failure)
    $intakeException = $Failure.Exception
    while ($null -ne $intakeException) {
        if ($intakeException.Data.Contains('local_intake_reason')) {
            return [string]$intakeException.Data['local_intake_reason']
        }
        $intakeException = $intakeException.InnerException
    }
    throw $Failure
}

Export-ModuleMember -Function @(
    'Stop-IntakePrimitive', 'Get-IntakeSha', 'Convert-IntakeClock', 'Get-IntakeUtcNs',
    'Skip-IntakeWhitespace', 'Read-IntakeString', 'Read-IntakeValue', 'Read-IntakeJson',
    'Convert-IntakeQuoted', 'Compare-IntakeScalarKeys', 'Convert-IntakeCanonicalText',
    'Convert-IntakeCanonicalBytes', 'Assert-IntakeKeys', 'Get-IntakeLiteralBytes',
    'Get-IntakeExpectedReason'
)
