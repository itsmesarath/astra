# Registered proof-only root observer. No target member/file acquisition.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$CaseId,
    [Parameter(Mandatory)][string]$LaunchSealPath,
    [Parameter(Mandatory)][string]$ExpectedExpectationsSha256,
    [Parameter(Mandatory)][string]$ObserverSha256,
    [Parameter(Mandatory)][string]$PrimitivesSha256
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:rootUtf8 = [Text.UTF8Encoding]::new($false, $true)
$script:rootUnicode = [Text.UnicodeEncoding]::new($false, $false, $true)
$script:rootInvariant = [Globalization.CultureInfo]::InvariantCulture
$script:rootHardEnd = [Numerics.BigInteger]::Parse('1792076348000000000', $script:rootInvariant)
$script:rootFrequency = [Diagnostics.Stopwatch]::Frequency
$script:rootLastTicks = [long]-1
$script:rootLastUtc = [Numerics.BigInteger]0
$script:rootLastUtcTicks = $null
$script:rootClockFailure = $null
$script:rootPrecedingManagedFailure = $null
$script:rootState = $null

function Stop-RootObservation {
    param([string]$Reason)
    $failure = [IO.InvalidDataException]::new('local-intake-observer:' + $Reason)
    $failure.Data['local_intake_reason'] = $Reason
    throw $failure
}

function Get-RootRawSha {
    param([byte[]]$Bytes)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
}

function Read-RootCapturedBytes {
    param([string]$Path, [long]$ExpectedLength, [string]$ExpectedSha, [int]$Cap)
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $ExpectedLength -le 0 -or
        $ExpectedLength -gt $Cap -or $ExpectedSha -cnotmatch '\A[0-9a-f]{64}\z') {
        Stop-RootObservation 'metadata_context'
    }
    $capture = [byte[]]::new($Cap + 1)
    $inputFile = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $actual = $inputFile.Read($capture, 0, $capture.Length)
        if ($actual -ne $ExpectedLength -or $actual -gt $Cap) { Stop-RootObservation 'metadata_length' }
        $probe = [byte[]]::new(1)
        if ($inputFile.Read($probe, 0, 1) -ne 0) { Stop-RootObservation 'metadata_eof' }
    }
    finally { $inputFile.Dispose() }
    $complete = [byte[]]::new($actual)
    [Array]::Copy($capture, 0, $complete, 0, $actual)
    if ((Get-RootRawSha $complete) -cne $ExpectedSha) { Stop-RootObservation 'metadata_pin' }
    return ,$complete
}

function Get-RootClock {
    $ticks = [Diagnostics.Stopwatch]::GetTimestamp()
    $utcTicks = [DateTime]::UtcNow.Ticks
    $utc = ([Numerics.BigInteger]$utcTicks - [Numerics.BigInteger][DateTime]::UnixEpoch.Ticks) * 100
    $reason = $null
    if ($ticks -lt $script:rootLastTicks) { $reason = 'monotonic_decrease' }
    elseif ($utc -lt $script:rootLastUtc -or $utc -lt 0) { $reason = 'utc_decrease_or_negative' }
    elseif ($utc -ge $script:rootHardEnd -and
        ($null -eq $script:rootState -or -not $script:rootState.CleanupPhase)) { $reason = 'hard_deadline' }
    $converted = $null; $conversionError = $null
    if ($null -eq $reason) {
        try { $converted = Convert-IntakeClock $ticks $script:rootFrequency }
        catch { $reason = 'clock_conversion'; $conversionError = Convert-RootError $_ }
    }
    if ($null -ne $reason -or $null -ne $script:rootClockFailure) {
        if ($null -eq $script:rootClockFailure) {
            $script:rootClockFailure = [ordered]@{
                reason = $reason; actual_stopwatch_ticks_i64 = $ticks; actual_frequency_i64 = $script:rootFrequency
                actual_utc_ticks_i64 = $utcTicks; actual_utc_unix_ns = $utc
                previous_stopwatch_ticks_i64 = $script:rootLastTicks; previous_utc_ticks_i64 = $script:rootLastUtcTicks
                previous_utc_unix_ns = $script:rootLastUtc; conversion_error = $conversionError
            }
        }
        $failure = [IO.InvalidDataException]::new('local-intake-observer:sticky-clock-fault:' + (Convert-IntakeCanonicalText $script:rootClockFailure))
        $failure.Data['local_intake_reason'] = 'clock'
        $failure.Data['clock_observation'] = $script:rootClockFailure
        throw $failure
    }
    $script:rootLastTicks = $ticks
    $script:rootLastUtc = $utc
    $script:rootLastUtcTicks = $utcTicks
    return $converted
}

function Invoke-RootEmergencyCleanup {
    param([Management.Automation.ErrorRecord]$OriginalFailure)
    # This is an explicitly UNQUALIFIED safety path. It never supplies invented P2 timestamps.
    # No clock, PID query, process creation, task creation or new native proof handle occurs here.
    $actions = [Collections.Generic.List[object]]::new()
    $diagnostic = [ordered]@{
        version = 'local-intake-unqualified-clock-cleanup-v1'; qualification = 'incomplete'
        clock_observation = $script:rootClockFailure; original_exception = Convert-RootError $OriginalFailure
        preceding_managed_exception = if ($null -eq $script:rootPrecedingManagedFailure) { $null } else { Convert-RootError $script:rootPrecedingManagedFailure }
        retained_observer = if ($null -eq $script:rootState) { $null } else { $script:rootState.Observer }
        retained_host_creation = if ($null -eq $script:rootState) { $null } else { $script:rootState.HostCreation }
        actions = @(); unresolved_task_ids = @(); carrier_complete = $true
    }
    $perform = {
        param([string]$Operation, [int]$Id)
        $row = [ordered]@{ ordinal = $actions.Count; operation = $Operation; retained_id = $Id; state = 'pending'; result = $null; error = $null; after_buffer_hex = $null }
        try {
            switch -CaseSensitive ($Operation) {
                'Process.Kill' { $script:rootState.KillAttempted = $true; $script:rootState.Processes[1].Kill($false); $row.result = [ordered]@{ kind = 'void'; value = $null } }
                'Process.WaitForExit' { $row.result = [ordered]@{ kind = 'bool'; value = $script:rootState.Processes[1].WaitForExit(0) } }
                'Stream.Dispose' { $script:rootState.Streams[$Id].Dispose(); $row.result = [ordered]@{ kind = 'void'; value = $null } }
                'Task.IsCompleted' { $row.result = [ordered]@{ kind = 'bool'; value = [bool]$script:rootState.Tasks[$Id].task.IsCompleted } }
                'Task.GetResult' {
                    $entry = $script:rootState.Tasks[$Id]
                    if ($entry.creator -ceq 'Stream.ReadAsync') {
                        $value = $entry.task.GetAwaiter().GetResult()
                        $row.result = [ordered]@{ kind = 'i32'; value = $value }
                        $row.after_buffer_hex = [Convert]::ToHexString($script:rootState.Buffers[[int]$entry.buffer_id]).ToLowerInvariant()
                    }
                    else { $entry.task.GetAwaiter().GetResult(); $row.result = [ordered]@{ kind = 'void'; value = $null } }
                    $entry.settled = $true
                }
                'Process.Dispose' { $script:rootState.Processes[$Id].Dispose(); $row.result = [ordered]@{ kind = 'void'; value = $null } }
                default { throw [IO.InvalidDataException]::new('unregistered emergency action') }
            }
            $row.state = 'completed'
        }
        catch {
            $row.state = 'faulted'; $row.result = $null; $row.error = Convert-RootError $_
            if ($Operation -ceq 'Task.GetResult') {
                $entry = $script:rootState.Tasks[$Id]; $entry.settled = $true
                if ($entry.creator -ceq 'Stream.ReadAsync') {
                    $row.after_buffer_hex = [Convert]::ToHexString($script:rootState.Buffers[[int]$entry.buffer_id]).ToLowerInvariant()
                }
            }
        }
        # Recording cannot prevent the fixed retained-object safety actions themselves.
        try { $actions.Add($row) } catch { $diagnostic.carrier_complete = $false }
        return $row
    }
    if ($null -ne $script:rootState -and $script:rootState.HostStarted -and
        $script:rootState.Processes.ContainsKey(1)) {
        if ($script:rootState.Terminal.host_signalled -cne $true) {
            if (-not $script:rootState.KillAttempted) { $null = & $perform 'Process.Kill' 1 }
            for ($probe = 0; $probe -lt 64; $probe++) {
                $row = & $perform 'Process.WaitForExit' 1
                if ($row.state -ceq 'completed' -and $row.result.value -ceq $true) {
                    $script:rootState.Terminal.host_signalled = $true; break
                }
            }
        }
        foreach ($id in @(0, 1, 2)) {
            if ($script:rootState.Streams.ContainsKey($id) -and -not $script:rootState.CloseAttempted[$id]) {
                $script:rootState.CloseAttempted[$id] = $true
                $null = & $perform 'Stream.Dispose' $id
            }
        }
        for ($id = 0; $id -lt $script:rootState.Tasks.Count; $id++) {
            if (-not $script:rootState.Tasks[$id].settled) {
                $row = & $perform 'Task.IsCompleted' $id
                if ($row.state -ceq 'completed' -and $row.result.value -ceq $true) {
                    $null = & $perform 'Task.GetResult' $id
                }
            }
        }
    }
    if ($null -ne $script:rootState) {
        foreach ($id in @(1, 0)) {
            if ($script:rootState.Processes.ContainsKey($id) -and -not $script:rootState.ProcessDisposeAttempted.Contains($id)) {
                $null = $script:rootState.ProcessDisposeAttempted.Add($id)
                $null = & $perform 'Process.Dispose' $id
            }
        }
        $unresolved = [Collections.Generic.List[int]]::new()
        for ($id = 0; $id -lt $script:rootState.Tasks.Count; $id++) {
            if (-not $script:rootState.Tasks[$id].settled) { $unresolved.Add($id) }
        }
        $diagnostic.unresolved_task_ids = $unresolved.ToArray()
    }
    $diagnostic.actions = $actions.ToArray()
    try {
        $bytes = Convert-IntakeCanonicalBytes $diagnostic
        if ($bytes.Length -gt 1048576) { throw [IO.InvalidDataException]::new('complete emergency diagnostic exceeds reserved cap; carrier missing') }
        $OriginalFailure.Exception.Data['unqualified_emergency_cleanup'] = $diagnostic
        [Console]::Error.WriteLine($script:rootUtf8.GetString($bytes))
    }
    catch {
        # The original exception remains authoritative; no partial diagnostic is called complete.
        $OriginalFailure.Exception.Data['unqualified_emergency_carrier_missing'] = $true
    }
}

function Convert-RootHex {
    param([string]$Text, [int]$MaxUnits)
    if ($Text.Length -gt $MaxUnits) { Stop-RootObservation 'text_first_excess' }
    return [Convert]::ToHexString($script:rootUnicode.GetBytes($Text)).ToLowerInvariant()
}

function Convert-RootDate {
    param([DateTime]$Date, [int]$Quantum)
    $record = [ordered]@{
        managed_type = 'System.DateTime'; kind = $Date.Kind.ToString(); ticks_i64 = $Date.Ticks
        roundtrip_text = $Date.ToString('O', $script:rootInvariant); utc_ticks_i64 = $null
        filetime_u64 = $null; quantum_100ns = $Quantum; conversion_state = 'invalid'
    }
    if ($Date.Kind -eq [DateTimeKind]::Unspecified) { return $record }
    if ($Date.Kind -eq [DateTimeKind]::Local -and
        ([TimeZoneInfo]::Local.IsInvalidTime($Date) -or [TimeZoneInfo]::Local.IsAmbiguousTime($Date))) {
        return $record
    }
    try {
        $utc = $Date.ToUniversalTime()
        $filetime = $utc.ToFileTimeUtc()
        if ($filetime -lt 0 -or $utc.Ticks % $Quantum -ne 0 -or $filetime % $Quantum -ne 0) {
            return $record
        }
        $record.utc_ticks_i64 = $utc.Ticks
        $record.filetime_u64 = [ulong]$filetime
        $record.conversion_state = 'valid'
    }
    catch { return $record }
    return $record
}

function Convert-RootError {
    param([Management.Automation.ErrorRecord]$Failure)
    $exception = $Failure.Exception
    $message = $exception.Message
    $complete = $message.Length -le 8192
    # Complete text is never shortened to manufacture an admissible error.
    return [ordered]@{
        type_name = $exception.GetType().FullName; hresult_i32 = $exception.HResult
        fully_qualified_error_id = $Failure.FullyQualifiedErrorId
        message_utf16le_hex = [Convert]::ToHexString($script:rootUnicode.GetBytes($message)).ToLowerInvariant()
        complete = $complete
    }
}

function Assert-RootEqual {
    param([object]$Actual, [object]$Expected, [string]$Reason)
    if ((Convert-IntakeCanonicalText $Actual) -cne (Convert-IntakeCanonicalText $Expected)) {
        Stop-RootObservation $Reason
    }
}

function Read-RootCanonicalArtifact {
    param([object]$Reference, [int]$Cap)
    Assert-IntakeKeys $Reference @('path', 'raw_byte_length', 'raw_sha256', 'canonical_byte_length', 'canonical_sha256')
    Assert-RootInteger $Reference['raw_byte_length'] 1 $Cap
    Assert-RootInteger $Reference['canonical_byte_length'] 1 $Cap
    if ($Reference['path'] -isnot [string] -or $Reference['raw_sha256'] -isnot [string] -or
        $Reference['canonical_sha256'] -isnot [string] -or
        $Reference['canonical_sha256'] -cnotmatch '\A[0-9a-f]{64}\z') { Stop-RootObservation 'artifact_domain' }
    $bytes = Read-RootCapturedBytes $Reference['path'] ([long]$Reference['raw_byte_length']) $Reference['raw_sha256'] $Cap
    $value = Read-IntakeJson $bytes
    $canonical = Convert-IntakeCanonicalBytes $value
    if ($canonical.Length -gt $Cap -or $canonical.Length -ne $Reference['canonical_byte_length'] -or
        (Get-IntakeSha $canonical) -cne $Reference['canonical_sha256']) {
        Stop-RootObservation 'metadata_canonical_pin'
    }
    return [ordered]@{ raw = $bytes; canonical = $canonical; value = $value }
}

function Get-RootMetadataSize {
    if ($null -eq $script:rootState) { return 0 }
    $sizeView = [ordered]@{
        observer = $script:rootState.Observer; host_creation = $script:rootState.HostCreation
        managed_calls = $script:rootState.Calls.ToArray(); queries = $script:rootState.Queries.ToArray()
        request = $script:rootState.Request; ack = $script:rootState.Ack
        artifacts = $script:rootState.Artifacts.ToArray(); terminal = $script:rootState.Terminal
        polls = $script:rootState.Polls.ToArray(); waits = $script:rootState.Waits.ToArray()
        closes = $script:rootState.Closes.ToArray(); frames = $script:rootState.Frames.ToArray()
        authority_flags = $script:rootState.Flags
    }
    return (Convert-IntakeCanonicalBytes $sizeView).Length
}

function Assert-RootReservation {
    param([int]$MetadataBytes = 65536)
    $null = Get-RootClock
    # Reserve actual cleanup rows/metadata inside, not in addition to, the registered absolute caps.
    # Ordinary side effects refuse before consuming this reserve; insufficient cleanup never passes.
    $rowReserve = if ($script:rootState.CleanupPhase) { 0 } else { 256 }
    $metadataReserve = if ($script:rootState.CleanupPhase) { 0 } else { 1048576 }
    if ((Get-RootMetadataSize) + $MetadataBytes + $metadataReserve -gt 16777216 -or
        $script:rootState.Calls.Count + $rowReserve -ge 4352) { Stop-RootObservation 'budget' }
}

function Save-RootArtifact {
    param([string]$Role, [string]$RelativePath, [byte[]]$Bytes,
        [bool]$Complete, [string]$Provenance, [AllowNull()][object]$TransferredCount)
    if ($script:rootState.Artifacts.Count -gt 2051 -or $RelativePath -cnotmatch '\A[a-z0-9_]+\.bin\z') {
        Stop-RootObservation 'artifact_context'
    }
    if ($script:rootState.ArtifactNames.Contains($RelativePath)) { Stop-RootObservation 'artifact_duplicate' }
    if ($script:rootState.RawArtifactBytes + $Bytes.Length -gt 335544320) { Stop-RootObservation 'budget' }
    $absolute = [IO.Path]::Combine($script:rootState.OutputDirectory, $RelativePath)
    $stream = [IO.FileStream]::new($absolute, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($Bytes, 0, $Bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    $ordinal = switch -CaseSensitive ($RelativePath) {
        'host_stdout.bin' { 0 }
        'host_stderr.bin' { 1 }
        'root_stdin_prepared.bin' { 2 }
        default {
            if ($RelativePath -cnotmatch '\Aread_buffer_([0-9]{4})\.bin\z') { Stop-RootObservation 'artifact_context' }
            $readOrdinal = [int]::Parse($Matches[1], $script:rootInvariant)
            if ($readOrdinal -ge 2048) { Stop-RootObservation 'artifact_context' }
            $readOrdinal + 3
        }
    }
    if ($ordinal -ge $script:rootState.Artifacts.Count -or $null -ne $script:rootState.Artifacts[$ordinal]) {
        Stop-RootObservation 'artifact_ordinal'
    }
    $record = [ordered]@{
        ordinal = $ordinal; role = $Role; relative_path = $RelativePath; byte_length = $Bytes.Length
        sha256 = Get-IntakeSha $Bytes; complete = $Complete; provenance = $Provenance
        transferred_byte_count = $TransferredCount
    }
    $script:rootState.Artifacts[$ordinal] = $record
    $null = $script:rootState.ArtifactNames.Add($RelativePath)
    $script:rootState.RawArtifactBytes += $Bytes.Length
    return $record
}

function New-RootValue {
    param([string]$Kind, [AllowNull()][object]$Value)
    return [ordered]@{ kind = $Kind; value = $Value }
}

function New-RootRef {
    param([string]$Kind, [int]$Id)
    return [ordered]@{ kind = $Kind; id = $Id }
}

function Invoke-RootManaged {
    param([string]$Operation, [AllowNull()][object]$Receiver, [object[]]$Values = @())
    Assert-RootReservation
    $row = [ordered]@{
        ordinal = $script:rootState.Calls.Count; operation = $Operation
        started_monotonic_ns = Get-RootClock; ended_monotonic_ns = $null
        arguments = [ordered]@{ receiver = $Receiver; values = $Values }
        state = 'pending'; result = $null; error = $null; buffer_artifact = $null
    }
    $script:rootState.Calls.Add($row)
    $taskEntry = $null
    $actual = $null
    try {
        switch -CaseSensitive ($Operation) {
            'Process.GetCurrentProcess' {
                $script:rootState.Processes[0] = [Diagnostics.Process]::GetCurrentProcess()
                $row.result = New-RootValue 'local_ref' (New-RootRef 'process' 0)
            }
            'Process.Start' {
                $script:rootState.HostCreation.start_attempted = $true
                $actual = $script:rootState.Processes[1].Start()
                $row.result = New-RootValue 'bool' $actual
                $row.state = 'completed'
                if ($actual) {
                    # Ownership is established by the actual return even if a later clock check refuses.
                    $script:rootState.HostStarted = $true
                    $script:rootState.HostCreation.start_return = $true
                    $script:rootState.Streams[0] = $script:rootState.Processes[1].StandardInput.BaseStream
                    $script:rootState.Streams[1] = $script:rootState.Processes[1].StandardOutput.BaseStream
                    $script:rootState.Streams[2] = $script:rootState.Processes[1].StandardError.BaseStream
                    $globalLimit = [Numerics.BigInteger]$row.started_monotonic_ns + ($script:rootHardEnd - $script:rootLastUtc)
                    $workLimit = [Numerics.BigInteger]$row.started_monotonic_ns + 30000000000
                    $script:rootState.Terminal.work_deadline_monotonic_ns = [ulong][Numerics.BigInteger]::Min($globalLimit, $workLimit)
                }
            }
            'Process.Id' {
                $actual = $script:rootState.Processes[[int]$Receiver.id].Id
                $row.result = New-RootValue 'i32' $actual
            }
            'Process.Handle' {
                $handle = $script:rootState.Processes[[int]$Receiver.id].Handle.ToInt64()
                $actual = [BitConverter]::ToUInt64([BitConverter]::GetBytes($handle), 0)
                $row.result = New-RootValue 'u64' $actual
            }
            'Process.StartTime' {
                $actual = Convert-RootDate $script:rootState.Processes[[int]$Receiver.id].StartTime 1
                $row.result = New-RootValue 'date_time' $actual
            }
            'Process.MainModule.FileName' {
                $actual = Convert-RootHex $script:rootState.Processes[[int]$Receiver.id].MainModule.FileName 512
                $row.result = New-RootValue 'utf16le_hex' $actual
            }
            'Process.HasExited' {
                $actual = $script:rootState.Processes[1].HasExited
                $row.result = New-RootValue 'bool' $actual
            }
            'Process.ExitCode' {
                if ($script:rootState.Terminal.host_signalled -cne $true) { Stop-RootObservation 'exit_before_signal' }
                $actual = $script:rootState.Processes[1].ExitCode
                $row.result = New-RootValue 'i32' $actual
            }
            'Stream.ReadAsync' {
                $allocationId = [int]$Values[0].value.id
                $buffer = $script:rootState.Buffers[$allocationId]
                $task = $script:rootState.Streams[[int]$Receiver.id].ReadAsync($buffer, 0, $buffer.Length)
                $taskId = $script:rootState.Tasks.Count
                $script:rootState.Tasks.Add([ordered]@{
                    task = $task; creator = $Operation; stream_id = [int]$Receiver.id
                    buffer_id = $allocationId; settled = $false; result = $null; error = $null
                    read_ordinal = $script:rootState.ReadOrdinalByBuffer[$allocationId]
                })
                $actual = $taskId
                $row.result = New-RootValue 'local_ref' (New-RootRef 'task' $taskId)
            }
            'Stream.WriteAsync' {
                $allocationId = [int]$Values[0].value.id
                $buffer = $script:rootState.Buffers[$allocationId]
                $task = $script:rootState.Streams[0].WriteAsync($buffer, 0, $buffer.Length)
                $taskId = $script:rootState.Tasks.Count
                $script:rootState.Tasks.Add([ordered]@{
                    task = $task; creator = $Operation; stream_id = 0; buffer_id = $allocationId
                    settled = $false; result = $null; error = $null
                })
                $actual = $taskId
                $row.result = New-RootValue 'local_ref' (New-RootRef 'task' $taskId)
            }
            'Stream.FlushAsync' {
                $task = $script:rootState.Streams[0].FlushAsync()
                $taskId = $script:rootState.Tasks.Count
                $script:rootState.Tasks.Add([ordered]@{
                    task = $task; creator = $Operation; stream_id = 0; buffer_id = $null
                    settled = $false; result = $null; error = $null
                })
                $actual = $taskId
                $row.result = New-RootValue 'local_ref' (New-RootRef 'task' $taskId)
            }
            'Task.GetResult' {
                $taskEntry = $script:rootState.Tasks[[int]$Receiver.id]
                if ($taskEntry.creator -ceq 'Stream.ReadAsync') {
                    $actual = $taskEntry.task.GetAwaiter().GetResult()
                    if ($actual -isnot [int] -or $actual -lt 0 -or
                        $actual -gt $script:rootState.Buffers[[int]$taskEntry.buffer_id].Length) {
                        Stop-RootObservation 'read_count'
                    }
                    $row.result = New-RootValue 'i32' $actual
                }
                else { $taskEntry.task.GetAwaiter().GetResult(); $row.result = New-RootValue 'void' $null }
                $taskEntry.result = $actual
            }
            'Process.WaitForExit' {
                $actual = $script:rootState.Processes[1].WaitForExit([int]$Values[0].value)
                $row.result = New-RootValue 'bool' $actual
            }
            'Process.Kill' {
                $script:rootState.KillAttempted = $true
                $script:rootState.Processes[1].Kill($false)
                $row.result = New-RootValue 'void' $null
            }
            'Stream.Dispose' {
                $script:rootState.CloseAttempted[[int]$Receiver.id] = $true
                $script:rootState.Streams[[int]$Receiver.id].Dispose()
                $row.result = New-RootValue 'void' $null
            }
            'Process.Dispose' {
                $null = $script:rootState.ProcessDisposeAttempted.Add([int]$Receiver.id)
                $script:rootState.Processes[[int]$Receiver.id].Dispose()
                $row.result = New-RootValue 'void' $null
            }
            default { Stop-RootObservation 'unregistered_managed_operation' }
        }
        $row.state = 'completed'
        $row.ended_monotonic_ns = Get-RootClock
    }
    catch {
        # A later clock-admission fault must not rewrite an actual managed return as a method exception.
        if ($row.state -ceq 'completed') { throw }
        $actualMethodFailure = $_
        $row.state = 'faulted'; $row.result = $null; $row.error = Convert-RootError $actualMethodFailure
        if ($null -ne $taskEntry) { $taskEntry.error = $row.error }
        try { $row.ended_monotonic_ns = Get-RootClock }
        catch {
            $script:rootPrecedingManagedFailure = $actualMethodFailure
            $_.Exception.Data['preceding_managed_exception'] = $row.error
            $_.Exception.Data['preceding_managed_error_record'] = $actualMethodFailure
            throw
        }
        throw $actualMethodFailure
    }
    finally {
        if ($null -ne $taskEntry) {
            $taskEntry.settled = $true
            if ($null -ne $taskEntry.buffer_id) {
                $buffer = $script:rootState.Buffers[[int]$taskEntry.buffer_id]
                if ($taskEntry.creator -ceq 'Stream.WriteAsync') { $artifact = $script:rootState.PreparedArtifact }
                else {
                    $relative = 'read_buffer_' + ([int]$taskEntry.read_ordinal).ToString('D4', $script:rootInvariant) + '.bin'
                    $artifact = Save-RootArtifact 'read_buffer' $relative $buffer $true 'allocated_buffer_storage' $null
                }
                $prefix = $null
                if ($row.state -ceq 'completed') {
                    if ($taskEntry.creator -ceq 'Stream.ReadAsync') { $prefix = $actual }
                    else { $prefix = $buffer.Length }
                }
                $row.buffer_artifact = [ordered]@{
                    allocation_id = $taskEntry.buffer_id; artifact_ordinal = $artifact.ordinal
                    relative_path = $artifact.relative_path; byte_length = $artifact.byte_length
                    sha256 = $artifact.sha256; valid_prefix_bytes = $prefix
                }
            }
        }
    }
    return ,$row.result
}

function Test-RootTaskComplete {
    param([int]$TaskId)
    if ($script:rootState.Polls.Count -ge 65536) { Stop-RootObservation 'poll_budget' }
    Assert-RootReservation
    $entry = $script:rootState.Tasks[$TaskId]
    $complete = [bool]$entry.task.IsCompleted
    $role = @('stdin', 'stdout', 'stderr')[[int]$entry.stream_id]
    $script:rootState.Polls.Add([ordered]@{
        ordinal = $script:rootState.Polls.Count; task_id = $TaskId; stream_role = $role
        is_completed = $complete; monotonic_ns = Get-RootClock
    })
    return $complete
}

function Start-RootRead {
    param([int]$StreamId)
    if ($script:rootState.ReadAttempts -ge 2048 -or $null -ne $script:rootState.ActiveReads[$StreamId]) {
        Stop-RootObservation 'read_budget_or_overlap'
    }
    $remaining = $script:rootState.StreamLimits[$StreamId] + 1 - $script:rootState.StreamBytes[$StreamId].Length
    $capacity = [int][Math]::Min(65536, $remaining)
    if ($capacity -le 0 -or $script:rootState.ReadBufferBytes + $capacity -gt 134217728) {
        Stop-RootObservation 'read_budget'
    }
    Assert-RootReservation
    $id = $script:rootState.Buffers.Count
    $script:rootState.Buffers.Add([byte[]]::new($capacity))
    $script:rootState.ReadOrdinalByBuffer.Add($id, $script:rootState.ReadAttempts)
    $script:rootState.Artifacts.Add($null)
    $script:rootState.ReadAttempts++
    $script:rootState.ReadBufferBytes += $capacity
    $allocation = New-RootValue 'buffer_allocation' ([ordered]@{ id = $id; capacity_bytes = $capacity })
    $result = Invoke-RootManaged 'Stream.ReadAsync' (New-RootRef 'stream' $StreamId) @(
        $allocation, (New-RootValue 'u32' 0), (New-RootValue 'u32' $capacity)
    )
    $script:rootState.ActiveReads[$StreamId] = [int]$result.value.id
}

function Complete-RootRead {
    param([int]$StreamId, [bool]$ContinueReading)
    $taskId = $script:rootState.ActiveReads[$StreamId]
    if ($null -eq $taskId -or -not (Test-RootTaskComplete $taskId)) { return }
    try {
        $result = Invoke-RootManaged 'Task.GetResult' (New-RootRef 'task' $taskId)
        $count = [int]$result.value
        $bufferId = [int]$script:rootState.Tasks[$taskId].buffer_id
        if ($count -eq 0) { $script:rootState.Eof[$StreamId] = $true }
        else {
            $script:rootState.StreamBytes[$StreamId].Write($script:rootState.Buffers[$bufferId], 0, $count)
            if ($script:rootState.StreamBytes[$StreamId].Length -gt $script:rootState.StreamLimits[$StreamId]) {
                Stop-RootObservation 'stream_first_excess'
            }
        }
    }
    finally { $script:rootState.ActiveReads[$StreamId] = $null }
    if ($ContinueReading -and -not $script:rootState.Eof[$StreamId]) { Start-RootRead $StreamId }
}

function Invoke-RootCim {
    param([string]$Role, [uint]$ProcessId)
    if ($ProcessId -eq 0 -or $script:rootState.Queries.Count -ge 3) { Stop-RootObservation 'query_context' }
    Assert-RootReservation 524288
    $pidText = $ProcessId.ToString('D', $script:rootInvariant)
    $queryText = "Get-CimInstance -Namespace 'root/cimv2' -ClassName 'Win32_Process' -Filter ('ProcessId = {0}' -f " +
        $pidText + ") -Property 'ProcessId','ParentProcessId','CreationDate','ExecutablePath','CommandLine' -OperationTimeoutSec 1 -ErrorAction Stop"
    $row = [ordered]@{
        role = $Role; state = 'query_failed'; query_text = $queryText
        query_sha256 = Get-IntakeSha $script:rootUtf8.GetBytes($queryText)
        started_monotonic_ns = Get-RootClock; ended_monotonic_ns = $null
        selected_instances = @(); excess_observed = $false; error = $null
    }
    $script:rootState.Queries.Add($row)
    $selected = [Collections.Generic.List[object]]::new()
    try {
        Get-CimInstance -Namespace 'root/cimv2' -ClassName 'Win32_Process' -Filter ('ProcessId = {0}' -f $pidText) -Property 'ProcessId','ParentProcessId','CreationDate','ExecutablePath','CommandLine' -OperationTimeoutSec 1 -ErrorAction Stop |
            ForEach-Object {
                if ($selected.Count -ge 2) { $row.excess_observed = $true; Stop-RootObservation 'query_count' }
                $image = $null; $command = $null; $creation = $null
                if ($null -ne $_.ExecutablePath) { $image = Convert-RootHex $_.ExecutablePath 512 }
                if ($null -ne $_.CommandLine) {
                    $maximum = if ($Role -ceq 'observer') { 32768 } else { 24576 }
                    $command = Convert-RootHex $_.CommandLine $maximum
                }
                if ($_.CreationDate -is [DateTime]) { $creation = Convert-RootDate $_.CreationDate 10 }
                if ($_.ProcessId -isnot [uint] -or $_.ParentProcessId -isnot [uint]) {
                    Stop-RootObservation 'query_value'
                }
                $selected.Add([ordered]@{
                    process_id = $_.ProcessId; parent_process_id = $_.ParentProcessId
                    executable_path_utf16le_hex = $image; command_line_utf16le_hex = $command; creation = $creation
                })
            }
        $row.state = if ($selected.Count -eq 0) { 'missing' } elseif ($selected.Count -eq 2) { 'multiple' } else { 'complete' }
        if ($selected.Count -eq 1) {
            $value = $selected[0]
            if ($value.process_id -ne $ProcessId -or $null -eq $value.executable_path_utf16le_hex -or
                $null -eq $value.command_line_utf16le_hex -or $null -eq $value.creation -or
                $value.creation.conversion_state -cne 'valid') { $row.state = 'invalid' }
        }
    }
    catch { $row.state = 'query_failed'; $row.error = Convert-RootError $_ }
    finally { $row.selected_instances = $selected.ToArray(); $row.ended_monotonic_ns = Get-RootClock }
    return $row
}

function Read-RootBoundedBody {
    param([string]$Path, [int]$Cap)
    if (-not [IO.Path]::IsPathFullyQualified($Path)) { Stop-RootObservation 'metadata_path' }
    $buffer = [byte[]]::new($Cap + 1)
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $count = $stream.Read($buffer, 0, $buffer.Length)
        if ($count -gt $Cap) { Stop-RootObservation 'metadata_length' }
        $probe = [byte[]]::new(1)
        if ($stream.Read($probe, 0, 1) -ne 0) { Stop-RootObservation 'metadata_eof' }
    }
    finally { $stream.Dispose() }
    $complete = [byte[]]::new($count)
    [Array]::Copy($buffer, 0, $complete, 0, $count)
    return ,$complete
}

function Assert-RootOwnDigest {
    param([object]$Value, [string]$Field)
    if ($Value -isnot [Collections.IDictionary] -or -not $Value.ContainsKey($Field) -or
        $Value[$Field] -isnot [string] -or $Value[$Field] -cnotmatch '\A[0-9a-f]{64}\z') {
        Stop-RootObservation 'own_digest'
    }
    $body = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
    foreach ($key in $Value.Keys) { if ($key -cne $Field) { $body.Add($key, $Value[$key]) } }
    if ((Get-IntakeSha (Convert-IntakeCanonicalBytes $body)) -cne $Value[$Field]) {
        Stop-RootObservation 'own_digest'
    }
}

function Assert-RootRawReference {
    param([object]$Reference, [int]$Cap)
    Assert-IntakeKeys $Reference @('path', 'raw_byte_length', 'raw_sha256')
    Assert-RootInteger $Reference['raw_byte_length'] 0 $Cap
    if ($Reference['path'] -isnot [string] -or $Reference['raw_sha256'] -isnot [string] -or
        $Reference['raw_sha256'] -cnotmatch '\A[0-9a-f]{64}\z') { Stop-RootObservation 'raw_domain' }
    if ($Reference['raw_byte_length'] -eq 0) {
        $bytes = Read-RootBoundedBody $Reference['path'] $Cap
        if ($bytes.Length -ne 0 -or (Get-IntakeSha $bytes) -cne $Reference['raw_sha256']) {
            Stop-RootObservation 'raw_pin'
        }
    }
    else {
        $bytes = Read-RootCapturedBytes $Reference['path'] ([long]$Reference['raw_byte_length']) $Reference['raw_sha256'] $Cap
    }
    return ,$bytes
}

function Assert-RootStaticFile {
    param([string]$Path, [long]$Length, [string]$Sha)
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $Length -le 0 -or $Length -gt 67108864 -or
        $Sha -cnotmatch '\A[0-9a-f]{64}\z') { Stop-RootObservation 'static_pin_context' }
    $hasher = [Security.Cryptography.IncrementalHash]::CreateHash([Security.Cryptography.HashAlgorithmName]::SHA256)
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $buffer = [byte[]]::new(65536)
    $total = [long]0
    try {
        while ($total -lt $Length) {
            $requested = [int][Math]::Min(65536, $Length - $total)
            $count = $stream.Read($buffer, 0, $requested)
            if ($count -le 0 -or $count -gt $requested) { Stop-RootObservation 'static_length' }
            $hasher.AppendData($buffer, 0, $count)
            $total += $count
        }
        if ($stream.Read($buffer, 0, 1) -ne 0) { Stop-RootObservation 'static_eof' }
        $actualSha = [Convert]::ToHexString($hasher.GetHashAndReset()).ToLowerInvariant()
    }
    finally { $stream.Dispose(); $hasher.Dispose() }
    if ($total -ne $Length -or $actualSha -cne $Sha) { Stop-RootObservation 'static_pin' }
}

function Assert-RootStartup {
    param([object]$Registration)
    $startup = $Registration['process_contract']['site_startup']
    foreach ($directory in $startup['expected_global_pth_name_cohort']) {
        $names = [Collections.Generic.List[string]]::new()
        foreach ($file in [IO.Directory]::EnumerateFiles($directory['path'], '*', [IO.SearchOption]::TopDirectoryOnly)) {
            $name = [IO.Path]::GetFileName($file)
            if (-not $name.StartsWith('.', [StringComparison]::Ordinal) -and
                $name.EndsWith('.pth', [StringComparison]::Ordinal)) { $names.Add($name) }
        }
        $actual = $names.ToArray()
        [Array]::Sort($actual, [StringComparer]::Ordinal)
        Assert-RootEqual $actual $directory['names'] 'startup_pth_changed'
    }
    foreach ($candidate in $startup['exact_customization_and_override_candidates']) {
        if ($candidate['state'] -cne 'absent' -or [IO.File]::Exists($candidate['path']) -or
            [IO.Directory]::Exists($candidate['path'])) { Stop-RootObservation 'startup_candidate_changed' }
    }
}

function Assert-RootIdentity {
    param([object]$Query, [object]$Expected, [uint]$ParentId, [AllowNull()][object]$ManagedBirth)
    if ($Query['state'] -cne 'complete' -or $Query['excess_observed'] -cne $false -or
        $Query['selected_instances'].Length -ne 1 -or $null -ne $Query['error']) {
        Stop-RootObservation 'query_failure'
    }
    $actual = $Query['selected_instances'][0]
    if ($actual['process_id'] -ne $Expected['pid'] -or $actual['parent_process_id'] -ne $ParentId -or
        $actual['executable_path_utf16le_hex'] -cne $Expected['image_utf16le_hex'] -or
        $actual['command_line_utf16le_hex'] -cne $Expected['command_utf16le_hex'] -or
        $null -eq $actual['creation'] -or $actual['creation']['conversion_state'] -cne 'valid') {
        Stop-RootObservation 'identity_mismatch'
    }
    $left = [Numerics.BigInteger]::Divide([Numerics.BigInteger]$actual['creation']['filetime_u64'], 10)
    $right = [Numerics.BigInteger]::Divide([Numerics.BigInteger]$Expected['creation_filetime_u64'], 10)
    if ($left -ne $right) { Stop-RootObservation 'timestamp' }
    if ($null -ne $ManagedBirth -and ($ManagedBirth['conversion_state'] -cne 'valid' -or
        [Numerics.BigInteger]::Divide([Numerics.BigInteger]$ManagedBirth['filetime_u64'], 10) -ne $right)) {
        Stop-RootObservation 'timestamp'
    }
}

function Get-RootFrame {
    param([byte[]]$Bytes, [int]$Offset, [string]$Magic, [int]$Cap)
    if ($Offset -lt 0 -or $Bytes.Length - $Offset -lt 8) { return $null }
    if ([Text.Encoding]::ASCII.GetString($Bytes, $Offset, 4) -cne $Magic) { Stop-RootObservation 'frame_magic' }
    $length = [BitConverter]::ToUInt32($Bytes, $Offset + 4)
    if ($length -le 0 -or $length -gt $Cap) { Stop-RootObservation 'frame_length' }
    if ($Bytes.Length - $Offset - 8 -lt $length) { return $null }
    $body = [byte[]]::new($length)
    [Array]::Copy($Bytes, $Offset + 8, $body, 0, $length)
    $parsed = Read-IntakeJson $body
    if ([Convert]::ToHexString((Convert-IntakeCanonicalBytes $parsed)) -cne [Convert]::ToHexString($body)) {
        Stop-RootObservation 'frame_canonical'
    }
    $frame = [byte[]]::new(8 + $length)
    [Array]::Copy($Bytes, $Offset, $frame, 0, $frame.Length)
    return [ordered]@{ offset = $Offset; body = $body; bytes = $frame; value = $parsed }
}

function Add-RootFrameIndex {
    param([string]$Role, [string]$ArtifactPath, [object]$Frame, [bool]$Complete)
    if ($script:rootState.Frames.Count -ge 3) { Stop-RootObservation 'frame_count' }
    $script:rootState.Frames.Add([ordered]@{
        ordinal = $script:rootState.Frames.Count; role = $Role; artifact_path = $ArtifactPath
        byte_offset = $Frame.offset; frame_bytes = $Frame.bytes.Length; body_bytes = $Frame.body.Length
        frame_sha256 = Get-IntakeSha $Frame.bytes; body_sha256 = Get-IntakeSha $Frame.body; complete = $Complete
    })
}

function Start-RootAcknowledgement {
    param([object]$RequestFrame)
    if ($script:rootState.NoHandoff -or $null -ne $script:rootState.Request) { Stop-RootObservation 'request_count' }
    $request = $RequestFrame.value
    Assert-IntakeKeys $request @('version', 'registration_sha256', 'case_id', 'nonce_hex', 'packet_sha256', 'host', 'worker', 'job_process_ids', 'request_sha256')
    foreach ($name in @('version', 'registration_sha256', 'case_id', 'nonce_hex', 'packet_sha256', 'request_sha256')) {
        if ($request[$name] -isnot [string]) { Stop-RootObservation 'request_domain' }
    }
    if ($request['version'] -cne 'local-intake-identity-request-v1' -or
        $request['registration_sha256'] -cne $script:rootState.RegistrationSha -or
        $request['case_id'] -cne $CaseId -or $request['nonce_hex'] -cne $script:rootState.Packet['nonce_hex'] -or
        $request['packet_sha256'] -cne $script:rootState.ExpectedPacketSha) { Stop-RootObservation 'request_context' }
    Assert-RootOwnDigest $request 'request_sha256'
    foreach ($role in @('host', 'worker')) {
        Assert-IntakeKeys $request[$role] @('pid', 'creation_filetime_u64', 'image_utf16le_hex', 'command_utf16le_hex')
        Assert-RootInteger $request[$role]['pid'] 1 4294967295
        Assert-RootInteger $request[$role]['creation_filetime_u64'] 0 18446744073709551615
        foreach ($name in @('image_utf16le_hex', 'command_utf16le_hex')) {
            if ($request[$role][$name] -isnot [string]) { Stop-RootObservation 'request_identity' }
        }
    }
    if ($request['job_process_ids'] -isnot [object[]] -or $request['job_process_ids'].Length -ne 1) {
        Stop-RootObservation 'request_identity'
    }
    Assert-RootInteger $request['job_process_ids'][0] 1 4294967295
    if ($request['host']['pid'] -ne $script:rootState.HostCreation.process_id -or
        $request['host']['command_utf16le_hex'] -cne (Convert-RootHex $script:rootState.HostInvocation['prepared_command_line'] 24576) -or
        $request['host']['image_utf16le_hex'] -cne $script:rootState.ExpectedImageHex -or
        $request['worker']['image_utf16le_hex'] -cne $script:rootState.ExpectedImageHex -or
        $request['worker']['command_utf16le_hex'] -cne $script:rootState.ExpectedWorkerCommandHex -or
        $request['job_process_ids'].Length -ne 1 -or
        $request['job_process_ids'][0] -ne $request['worker']['pid']) { Stop-RootObservation 'request_identity' }
    $script:rootState.Request = $request
    Add-RootFrameIndex 'request' 'host_stdout.bin' $RequestFrame $true
    $ackStart = Get-RootClock
    $script:rootState.Terminal.ack_deadline_monotonic_ns = [ulong][Math]::Min(
        [decimal]$script:rootState.Terminal.work_deadline_monotonic_ns, [decimal]$ackStart + 3000000000
    )
    $failure = $null
    try {
        $hostQuery = Invoke-RootCim 'host' ([uint]$request['host']['pid'])
        Assert-RootIdentity $hostQuery $request['host'] ([uint]$script:rootState.Observer.pid) $script:rootState.HostCreation.start_time
        $workerQuery = Invoke-RootCim 'worker' ([uint]$request['worker']['pid'])
        Assert-RootIdentity $workerQuery $request['worker'] ([uint]$request['host']['pid']) $null
        if ($request['host']['creation_filetime_u64'] -gt $request['worker']['creation_filetime_u64'] -or
            $script:rootState.Observer.start_time.filetime_u64 -gt $request['host']['creation_filetime_u64']) {
            Stop-RootObservation 'timestamp'
        }
        if ((Get-RootClock) -ge $script:rootState.Terminal.ack_deadline_monotonic_ns) { $failure = 'deadline' }
    }
    catch {
        $reason = Get-IntakeExpectedReason $_
        $failure = if ($reason -cin @('query_failure', 'query_count', 'query_value', 'timestamp', 'identity_mismatch', 'budget', 'deadline', 'transport')) { $reason } else { 'transport' }
    }
    $ack = [ordered]@{
        version = 'local-intake-identity-ack-v1'; registration_sha256 = $script:rootState.RegistrationSha
        case_id = $CaseId; nonce_hex = $request['nonce_hex']; request_sha256 = $request['request_sha256']
        observations = $script:rootState.Queries.ToArray()
        decision = if ($null -eq $failure) { 'allow' } else { 'refuse' }; failure_code = $failure
    }
    $ack['ack_sha256'] = Get-IntakeSha (Convert-IntakeCanonicalBytes $ack)
    $body = Convert-IntakeCanonicalBytes $ack
    if ($body.Length -gt 524288) { Stop-RootObservation 'ack_first_excess' }
    $frame = [byte[]]::new(8 + $body.Length)
    [Array]::Copy([Text.Encoding]::ASCII.GetBytes('LMA1'), 0, $frame, 0, 4)
    [Array]::Copy([BitConverter]::GetBytes([uint]$body.Length), 0, $frame, 4, 4)
    [Array]::Copy($body, 0, $frame, 8, $body.Length)
    $script:rootState.Ack = $ack
    $script:rootState.PreparedArtifact = Save-RootArtifact 'root_stdin' 'root_stdin_prepared.bin' $frame $true 'prepared_write_input' $null
    Add-RootFrameIndex 'ack' 'root_stdin_prepared.bin' ([ordered]@{ offset = 0; bytes = $frame; body = $body }) $false
    $bufferId = $script:rootState.Buffers.Count
    $script:rootState.Buffers.Add($frame)
    $allocation = New-RootValue 'buffer_allocation' ([ordered]@{ id = $bufferId; capacity_bytes = $frame.Length })
    $task = Invoke-RootManaged 'Stream.WriteAsync' (New-RootRef 'stream' 0) @($allocation, (New-RootValue 'u32' 0), (New-RootValue 'u32' $frame.Length))
    $script:rootState.ActiveStdinTask = [int]$task.value.id
}

function Complete-RootStdin {
    if ($null -eq $script:rootState.ActiveStdinTask) { return }
    $id = [int]$script:rootState.ActiveStdinTask
    if (-not (Test-RootTaskComplete $id)) { return }
    $creator = $script:rootState.Tasks[$id].creator
    $null = Invoke-RootManaged 'Task.GetResult' (New-RootRef 'task' $id)
    $script:rootState.ActiveStdinTask = $null
    if ($creator -ceq 'Stream.WriteAsync') {
        $script:rootState.WriteCompleted = $true
        $task = Invoke-RootManaged 'Stream.FlushAsync' (New-RootRef 'stream' 0)
        $script:rootState.ActiveStdinTask = [int]$task.value.id
    }
    else { $script:rootState.FlushCompleted = $true; Close-RootStream 0 }
}

function Close-RootStream {
    param([int]$Id)
    if ($script:rootState.CloseAttempted[$Id]) { return }
    $row = [ordered]@{ ordinal = $script:rootState.Closes.Count; role = @('stdin', 'stdout', 'stderr')[$Id]; attempted = $false; completed = $null; error = $null }
    $script:rootState.Closes.Add($row)
    try { $null = Invoke-RootManaged 'Stream.Dispose' (New-RootRef 'stream' $Id); $row.attempted = $true; $row.completed = $true; $script:rootState.Closed[$Id] = $true }
    catch {
        $row.attempted = $script:rootState.CloseAttempted[$Id]
        if ($row.attempted) { $row.completed = $true; $row.error = Convert-RootError $_ }
        throw
    }
}

function Wait-RootHost {
    param([int]$Milliseconds)
    if ($Milliseconds -lt 0 -or $Milliseconds -gt 20) { Stop-RootObservation 'wait_domain' }
    $deadline = if ($script:rootState.CleanupPhase) { $script:rootState.CleanupDeadline } else { $script:rootState.Terminal.work_deadline_monotonic_ns }
    if ($null -ne $deadline) {
        $remaining = [Numerics.BigInteger]$deadline - (Get-RootClock)
        if ($remaining -lt 0) { $remaining = 0 }
        $Milliseconds = [int][Math]::Min($Milliseconds, [decimal][Numerics.BigInteger]::Divide($remaining, 1000000))
    }
    $row = [ordered]@{
        ordinal = $script:rootState.Waits.Count; requested_ms = $Milliseconds
        started_monotonic_ns = Get-RootClock; ended_monotonic_ns = $null; returned_bool = $null; error = $null
    }
    $script:rootState.Waits.Add($row)
    try {
        $value = Invoke-RootManaged 'Process.WaitForExit' (New-RootRef 'process' 1) @((New-RootValue 'u32' $Milliseconds))
        $row.returned_bool = $value.value
        $row.ended_monotonic_ns = Get-RootClock
        $script:rootState.Terminal.host_signalled = $value.value
        return $value.value
    }
    catch { $row.ended_monotonic_ns = Get-RootClock; $row.error = Convert-RootError $_; throw }
}

function Assert-RootInteger {
    param([object]$Value, [Numerics.BigInteger]$Minimum, [Numerics.BigInteger]$Maximum)
    if (($Value -isnot [Numerics.BigInteger] -and $Value -isnot [int] -and $Value -isnot [uint] -and
        $Value -isnot [long] -and $Value -isnot [ulong]) -or
        [Numerics.BigInteger]$Value -lt $Minimum -or [Numerics.BigInteger]$Value -gt $Maximum) {
        Stop-RootObservation 'integer_domain'
    }
}

function Assert-RootDateShape {
    param([object]$Value, [int]$Quantum)
    Assert-IntakeKeys $Value @('managed_type', 'kind', 'ticks_i64', 'roundtrip_text', 'utc_ticks_i64', 'filetime_u64', 'quantum_100ns', 'conversion_state')
    Assert-RootInteger $Value['ticks_i64'] 0 3155378975999999999
    Assert-RootInteger $Value['utc_ticks_i64'] 0 3155378975999999999
    Assert-RootInteger $Value['filetime_u64'] 0 18446744073709551615
    Assert-RootInteger $Value['quantum_100ns'] $Quantum $Quantum
    if ($Value['managed_type'] -isnot [string] -or $Value['managed_type'] -cne 'System.DateTime' -or
        $Value['kind'] -isnot [string] -or $Value['kind'] -cnotin @('Utc', 'Local') -or
        $Value['roundtrip_text'] -isnot [string] -or $Value['conversion_state'] -cne 'valid') {
        Stop-RootObservation 'date_shape'
    }
    $kind = if ($Value['kind'] -ceq 'Utc') { [DateTimeKind]::Utc } else { [DateTimeKind]::Local }
    $date = [DateTime]::new([long]$Value['ticks_i64'], $kind)
    Assert-RootEqual (Convert-RootDate $date $Quantum) $Value 'date_projection'
}

function Assert-RootCompleteCimShape {
    param([object]$Value, [string]$Role, [uint]$ProcessId)
    Assert-IntakeKeys $Value @('role', 'state', 'query_text', 'query_sha256', 'started_monotonic_ns', 'ended_monotonic_ns', 'selected_instances', 'excess_observed', 'error')
    if ($Value['role'] -cne $Role -or $Value['state'] -cne 'complete' -or
        $Value['query_text'] -isnot [string] -or $Value['query_text'].Length -gt 1024 -or
        $Value['query_sha256'] -isnot [string] -or
        $Value['query_sha256'] -cne (Get-IntakeSha $script:rootUtf8.GetBytes($Value['query_text'])) -or
        $Value['selected_instances'] -isnot [object[]] -or $Value['selected_instances'].Length -ne 1 -or
        $Value['excess_observed'] -isnot [bool] -or $Value['excess_observed'] -cne $false -or
        $null -ne $Value['error']) { Stop-RootObservation 'cim_shape' }
    Assert-RootInteger $Value['started_monotonic_ns'] 0 18446744073709551615
    Assert-RootInteger $Value['ended_monotonic_ns'] $Value['started_monotonic_ns'] 18446744073709551615
    $pidText = $ProcessId.ToString('D', $script:rootInvariant)
    $text = "Get-CimInstance -Namespace 'root/cimv2' -ClassName 'Win32_Process' -Filter ('ProcessId = {0}' -f " +
        $pidText + ") -Property 'ProcessId','ParentProcessId','CreationDate','ExecutablePath','CommandLine' -OperationTimeoutSec 1 -ErrorAction Stop"
    if ($Value['query_text'] -cne $text) { Stop-RootObservation 'query_template' }
    $instance = $Value['selected_instances'][0]
    Assert-IntakeKeys $instance @('process_id', 'parent_process_id', 'executable_path_utf16le_hex', 'command_line_utf16le_hex', 'creation')
    Assert-RootInteger $instance['process_id'] 1 4294967295
    Assert-RootInteger $instance['parent_process_id'] 0 4294967295
    foreach ($name in @('executable_path_utf16le_hex', 'command_line_utf16le_hex')) {
        $limit = if ($name -ceq 'executable_path_utf16le_hex') { 512 } elseif ($Role -ceq 'observer') { 32768 } else { 24576 }
        if ($instance[$name] -isnot [string] -or $instance[$name] -cnotmatch '\A(?:[0-9a-f]{4})+\z' -or
            $instance[$name].Length -gt $limit * 4) { Stop-RootObservation 'cim_text' }
        $null = $script:rootUnicode.GetString([Convert]::FromHexString($instance[$name]))
    }
    Assert-RootDateShape $instance['creation'] 10
}

function Complete-RootCanonicalBody {
    param([byte[]]$Bytes)
    $value = Read-IntakeJson $Bytes
    if ([Convert]::ToHexString((Convert-IntakeCanonicalBytes $value)) -cne [Convert]::ToHexString($Bytes)) {
        Stop-RootObservation 'canonical_body'
    }
    return ,$value
}

function Get-RootRefForBody {
    param([string]$Path, [byte[]]$Bytes, [object]$Value)
    $canonical = Convert-IntakeCanonicalBytes $Value
    return [ordered]@{
        path = $Path; raw_byte_length = $Bytes.Length; raw_sha256 = Get-IntakeSha $Bytes
        canonical_byte_length = $canonical.Length; canonical_sha256 = Get-IntakeSha $canonical
    }
}

function Assert-RootContext {
    param([object]$Context, [string]$Role, [object]$Expected, [object]$Registration, [object]$WorkerRef)
    Assert-IntakeKeys $Context @('version', 'role', 'registration', 'protocol', 'declarations', 'source_manifest', 'runtime_manifest', 'expected_packet_sha256', 'hard_end_utc', 'hard_end_unix_ns', 'working_directory', 'worker_context')
    foreach ($name in @('version', 'role', 'expected_packet_sha256', 'hard_end_utc', 'working_directory')) {
        if ($Context[$name] -isnot [string]) { Stop-RootObservation 'context_domain' }
    }
    Assert-RootInteger $Context['hard_end_unix_ns'] $script:rootHardEnd $script:rootHardEnd
    if ($Context['version'] -cne 'local-member-intake-bootstrap-context-v1' -or $Context['role'] -cne $Role -or
        $Context['hard_end_utc'] -cne '2026-10-15T14:59:08Z' -or
        $Context['hard_end_unix_ns'] -ne $script:rootHardEnd -or
        $Context['working_directory'] -cne $Registration['process_contract']['working_directory'] -or
        $Context['expected_packet_sha256'] -cne $Expected['expected_packet_sha256']) {
        Stop-RootObservation 'context_binding'
    }
    foreach ($name in @('registration', 'protocol', 'declarations', 'source_manifest', 'runtime_manifest')) {
        Assert-RootEqual $Context[$name] $script:rootState.Expectations[$name] 'context_artifact_binding'
    }
    if ($Role -ceq 'worker') {
        if ($null -ne $Context['worker_context']) { Stop-RootObservation 'worker_context_role' }
    }
    else { Assert-RootEqual $Context['worker_context'] $WorkerRef 'independent_worker_context' }
}

function Assert-RootLaunchInputs {
    param([object]$Seal, [object]$Expectations)
    Assert-IntakeKeys $Seal @('version', 'expectations', 'observer', 'primitives', 'invocations', 'authority_flags')
    Assert-IntakeKeys $Expectations @('version', 'window_start_utc', 'hard_end_utc', 'registration', 'protocol', 'declarations', 'source_manifest', 'runtime_manifest', 'startup_policy', 'primitive_transfer', 'materializer', 'literal_artifacts', 'cases', 'authority_flags')
    if ($Seal['version'] -cne 'local-member-intake-bootstrap-launch-seal-v1' -or
        $Expectations['version'] -cne 'local-member-intake-bootstrap-expectations-v1' -or
        $Expectations['window_start_utc'] -cne '2026-10-15T06:59:08Z' -or
        $Expectations['hard_end_utc'] -cne '2026-10-15T14:59:08Z' -or
        $Seal['invocations'] -isnot [object[]] -or $Expectations['cases'] -isnot [object[]] -or
        $Seal['invocations'].Length -ne 24 -or $Expectations['cases'].Length -ne 24) {
        Stop-RootObservation 'launch_binding'
    }
    $registrationCapture = Read-RootCanonicalArtifact $Expectations['registration'] 1048576
    $registration = $registrationCapture.value
    if ($registration['schema'] -cne 'local-intake-bootstrap-registration-v2' -or
        $registration['window']['start_utc'] -cne '2026-10-15T06:59:08Z' -or
        $registration['window']['hard_end_utc'] -cne '2026-10-15T14:59:08Z') { Stop-RootObservation 'registration_revision' }
    Assert-RootEqual $Seal['authority_flags'] $registration['authority_flags'] 'authority_flags'
    Assert-RootEqual $Expectations['authority_flags'] $registration['authority_flags'] 'authority_flags'
    if ($registration['authority_flags'].Length -ne 28) { Stop-RootObservation 'authority_flags' }
    foreach ($flag in $registration['authority_flags']) {
        if ($flag -isnot [object[]] -or $flag.Length -ne 2 -or $flag[0] -isnot [string] -or
            $flag[1] -isnot [bool] -or $flag[1] -cne $false) { Stop-RootObservation 'authority_flags' }
    }
    $script:rootState.Registration = $registration
    $script:rootState.RegistrationSha = $Expectations['registration']['canonical_sha256']
    $script:rootState.Flags = $registration['authority_flags']
    $selected = $null; $invocation = $null
    for ($index = 0; $index -lt 24; $index++) {
        $case = $Expectations['cases'][$index]
        $call = $Seal['invocations'][$index]
        Assert-IntakeKeys $case @('ordinal', 'case_id', 'expected_base', 'submitted', 'rejected_evidence', 'worker_context', 'host_context', 'expected_packet_sha256', 'expected_template', 'host_invocation', 'outputs')
        Assert-IntakeKeys $call @('ordinal', 'case_id', 'script_path', 'parameters')
        if ($case['ordinal'] -ne $index -or $call['ordinal'] -ne $index -or
            $case['case_id'] -cne $registration['control_schedule'][$index]['case_id'] -or
            $call['case_id'] -cne $case['case_id']) { Stop-RootObservation 'cohort_order' }
        if ($case['case_id'] -ceq $CaseId) { $selected = $case; $invocation = $call }
    }
    if ($null -eq $selected -or $invocation['script_path'] -cne $Seal['observer']['path']) {
        Stop-RootObservation 'selected_case'
    }
    Assert-RootEqual $invocation['parameters'] ([ordered]@{
        CaseId = $CaseId; LaunchSealPath = $LaunchSealPath; ExpectedExpectationsSha256 = $ExpectedExpectationsSha256
        ObserverSha256 = $ObserverSha256; PrimitivesSha256 = $PrimitivesSha256
    }) 'observer_invocation'
    $script:rootState.Selected = $selected
    $script:rootState.OutputDirectory = $selected['outputs']['directory']
    $schedule = $registration['control_schedule'][[int]$selected['ordinal']]
    Assert-RootEqual $selected['outputs'] $schedule['outputs'] 'output_inventory'
    foreach ($pair in @(@('submitted', 'submitted'), @('expected_base', 'expected_base'), @('rejected_evidence', 'rejected_evidence'))) {
        if ($null -ne $selected[$pair[0]] -and $selected[$pair[0]]['path'] -cne $schedule['inputs'][$pair[1]]) {
            Stop-RootObservation 'input_path'
        }
    }
    if ($selected['worker_context']['path'] -cne $schedule['contexts']['worker'] -or
        $selected['host_context']['path'] -cne $schedule['contexts']['host']) { Stop-RootObservation 'context_path' }
    $template = $selected['expected_template']
    Assert-IntakeKeys $template @('declarations', 'case_selector', 'registry_selector', 'template_name')
    Assert-RootEqual $template['declarations'] $Expectations['declarations'] 'template_declarations'
    if ($template['case_selector'] -cne $schedule['expected_output_contract']['case_selector'] -or
        $template['registry_selector'] -cne $schedule['expected_output_contract']['complete_template_registry_selector'] -or
        $template['template_name'] -cne $schedule['expected_output_contract']['complete_template_name']) {
        Stop-RootObservation 'template_binding'
    }
    if (-not [IO.Directory]::Exists($script:rootState.OutputDirectory)) { Stop-RootObservation 'output_directory' }
    foreach ($name in @('root_receipt', 'host_receipt', 'host_stdout', 'host_stderr', 'root_stdin_prepared', 'owned_capture', 'tool_receipt')) {
        if ($selected['outputs'].ContainsKey($name) -and [IO.File]::Exists($selected['outputs'][$name])) {
            Stop-RootObservation 'output_exists'
        }
    }
    for ($bufferOrdinal = 0; $bufferOrdinal -lt 2048; $bufferOrdinal++) {
        $name = 'read_buffer_' + $bufferOrdinal.ToString('D4', $script:rootInvariant) + '.bin'
        if ([IO.File]::Exists([IO.Path]::Combine($script:rootState.OutputDirectory, $name))) {
            Stop-RootObservation 'buffer_output_exists'
        }
    }
    $protocolCapture = Read-RootCanonicalArtifact $Expectations['protocol'] 1048576
    $declarationsCapture = Read-RootCanonicalArtifact $Expectations['declarations'] 4194304
    foreach ($resource in $registration['existing_inputs']['json_resources']) {
        if ($resource['role'] -cin @('protocol', 'declarations')) {
            Assert-RootEqual $Expectations[$resource['role']] $resource['artifact'] 'registered_resource_pin'
        }
    }
    $sourceCapture = Read-RootCanonicalArtifact $Expectations['source_manifest'] 1048576
    $runtimeCapture = Read-RootCanonicalArtifact $Expectations['runtime_manifest'] 1048576
    $null = Assert-RootRawReference $Expectations['startup_policy'] 262144
    $null = Read-RootCanonicalArtifact $Expectations['primitive_transfer'] 4194304
    if ($Expectations['materializer']['path'] -cne $registration['artifact_contract']['materializer_path']) {
        Stop-RootObservation 'materializer_path'
    }
    $null = Assert-RootRawReference $Expectations['materializer'] 262144
    $script:rootState.Protocol = $protocolCapture.value
    $script:rootState.Declarations = $declarationsCapture.value
    Assert-RootEqual $protocolCapture.value['authority_flags'] $script:rootState.Flags 'authority_flags'
    Assert-RootEqual $declarationsCapture.value['authority_flags'] $script:rootState.Flags 'authority_flags'
    $source = $sourceCapture.value
    Assert-IntakeKeys $source @('version', 'registration_sha256', 'sources')
    if ($source['version'] -cne 'local-member-intake-bootstrap-source-manifest-v1' -or
        $source['registration_sha256'] -cne $script:rootState.RegistrationSha -or $source['sources'].Length -ne 6) {
        Stop-RootObservation 'source_manifest'
    }
    $roles = $registration['planned_sources']['source_manifest_membership']['exact_ordered_runtime_role_path_set']
    for ($index = 0; $index -lt 6; $index++) {
        $row = $source['sources'][$index]
        Assert-IntakeKeys $row @('role', 'path', 'raw_byte_length', 'raw_sha256')
        if ($row['role'] -cne $roles[$index]['role'] -or $row['path'] -cne $roles[$index]['path']) { Stop-RootObservation 'source_role' }
        Assert-RootInteger $row['raw_byte_length'] 1 262144
        $null = Read-RootCapturedBytes $row['path'] ([long]$row['raw_byte_length']) $row['raw_sha256'] 262144
        if ($row['role'] -ceq 'bootstrap_observer' -and $row['raw_sha256'] -cne $ObserverSha256) { Stop-RootObservation 'observer_source' }
        if ($row['role'] -ceq 'bootstrap_primitives' -and $row['raw_sha256'] -cne $PrimitivesSha256) { Stop-RootObservation 'primitive_source' }
    }
    $runtime = $runtimeCapture.value
    Assert-IntakeKeys $runtime @('version', 'registration_sha256', 'interpreter', 'static_modules', 'host_required_paths', 'worker_required_paths', 'exports')
    if ($runtime['version'] -cne 'local-member-intake-bootstrap-runtime-manifest-v1' -or
        $runtime['registration_sha256'] -cne $script:rootState.RegistrationSha) { Stop-RootObservation 'runtime_registration' }
    Assert-RootEqual $runtime['exports'] $registration['runtime_contract']['export_registrations'] 'export_registration'
    $allowlists = $registration['runtime_contract']['role_module_allowlists']
    if ($allowlists.Length -ne 2 -or $allowlists[0]['role'] -cne 'host_runtime' -or
        $allowlists[1]['role'] -cne 'worker_runtime') { Stop-RootObservation 'runtime_roles' }
    Assert-RootEqual $allowlists[1]['files'] $allowlists[0]['files'] 'same_fixed_native_allowlist'
    if ($runtime['static_modules'].Length -ne $allowlists[0]['files'].Length) { Stop-RootObservation 'runtime_module_count' }
    $seen = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
    for ($nativeIndex = 0; $nativeIndex -lt $runtime['static_modules'].Length; $nativeIndex++) {
        $row = $runtime['static_modules'][$nativeIndex]
        Assert-IntakeKeys $row @('role', 'absolute_path_utf16le_hex', 'byte_length', 'sha256')
        Assert-RootInteger $row['byte_length'] 1 67108864
        $path = $script:rootUnicode.GetString([Convert]::FromHexString($row['absolute_path_utf16le_hex']))
        $expectedFile = $allowlists[0]['files'][$nativeIndex]
        if ($row['role'] -cne 'host_runtime' -or $path -cne $expectedFile['absolute_path'] -or
            $row['byte_length'] -ne $expectedFile['byte_length'] -or
            $row['sha256'] -cne $expectedFile['sha256']) { Stop-RootObservation 'runtime_static_binding' }
        $identity = [ordered]@{ byte_length = $row['byte_length']; sha256 = $row['sha256'] }
        if ($seen.ContainsKey($path)) { Assert-RootEqual $identity $seen[$path] 'runtime_alias_identity' }
        else { Assert-RootStaticFile $path ([long]$row['byte_length']) $row['sha256']; $seen.Add($path, $identity) }
    }
    foreach ($role in $allowlists) {
        $requiredName = if ($role['role'] -ceq 'host_runtime') { 'host_required_paths' } else { 'worker_required_paths' }
        Assert-RootEqual $runtime[$requiredName] $role['required_paths'] 'runtime_required_paths'
    }
    Assert-RootEqual $runtime['interpreter'] ([ordered]@{
        role = 'interpreter'; path = $registration['runtime_contract']['interpreter_static_candidate']['path']
        byte_length = $registration['runtime_contract']['interpreter_static_candidate']['byte_length']
        sha256 = $registration['runtime_contract']['interpreter_static_candidate']['sha256']
    }) 'interpreter_pin'
    Assert-RootStartup $registration
    if ($Expectations['literal_artifacts'].Length -ne 14) { Stop-RootObservation 'literal_inventory' }
    for ($index = 0; $index -lt 14; $index++) {
        $row = $Expectations['literal_artifacts'][$index]
        Assert-IntakeKeys $row @('name', 'artifact')
        if ($row['name'] -cne $registration['artifact_contract']['literal_recipe_artifacts'][$index]['recipe_name']) {
            Stop-RootObservation 'literal_order'
        }
        if ($row['artifact']['path'] -cne $registration['artifact_contract']['literal_recipe_artifacts'][$index]['path']) {
            Stop-RootObservation 'literal_path'
        }
        $null = Assert-RootRawReference $row['artifact'] 4194305
    }
    $submitted = Assert-RootRawReference $selected['submitted'] 8193
    $script:rootState.ExpectedPacketSha = $selected['expected_packet_sha256']
    if ($null -ne $selected['expected_base']) {
        $base = Assert-RootRawReference $selected['expected_base'] 8193
        if ((Get-IntakeSha $base) -cne $selected['expected_packet_sha256']) { Stop-RootObservation 'original_packet_pin' }
    }
    elseif ($CaseId -cne 'packet_first_excess') { Stop-RootObservation 'original_packet_absence' }
    if ($null -ne $selected['rejected_evidence']) {
        if (-not $script:rootState.PureHost) { Stop-RootObservation 'rejected_evidence_scope' }
        $null = Read-RootCanonicalArtifact $selected['rejected_evidence'] 65536
    }
    elseif ($script:rootState.PureHost) { Stop-RootObservation 'missing_rejected_evidence' }
    $workerContext = Read-RootCanonicalArtifact $selected['worker_context'] 3072
    $hostContext = Read-RootCanonicalArtifact $selected['host_context'] 3072
    Assert-RootContext $workerContext.value 'worker' $selected $registration $null
    Assert-RootContext $hostContext.value 'host' $selected $registration $selected['worker_context']
    $hostInvocationRecord = $selected['host_invocation']
    Assert-IntakeKeys $hostInvocationRecord @('file_name', 'argument_list', 'prepared_command_line', 'working_directory', 'environment')
    $expectedArguments = @('-B', '-I', $roles[0]['path'], [Convert]::ToHexString($submitted).ToLowerInvariant(), [Convert]::ToHexString($hostContext.canonical).ToLowerInvariant())
    Assert-RootEqual $hostInvocationRecord['argument_list'] $expectedArguments 'host_arguments'
    if ($hostInvocationRecord['file_name'] -cne $registration['process_contract']['direct_interpreter'] -or
        $hostInvocationRecord['working_directory'] -cne $registration['process_contract']['working_directory'] -or
        $hostInvocationRecord['prepared_command_line'] -cne ('"' + $hostInvocationRecord['file_name'] + '" ' + [string]::Join(' ', $expectedArguments)) -or
        $hostInvocationRecord['prepared_command_line'].Length + 1 -gt 24576) { Stop-RootObservation 'host_invocation' }
    Assert-RootEqual $hostInvocationRecord['environment'] $registration['process_contract']['environment'] 'host_environment'
    $script:rootState.HostInvocation = $hostInvocationRecord
    $workerArguments = @('-B', '-I', $roles[1]['path'], [Convert]::ToHexString($submitted).ToLowerInvariant(), [Convert]::ToHexString($workerContext.canonical).ToLowerInvariant())
    $workerCommand = '"' + $hostInvocationRecord['file_name'] + '" ' + [string]::Join(' ', $workerArguments)
    if ($workerCommand.Length + 1 -gt 24576) { Stop-RootObservation 'worker_command' }
    $script:rootState.ExpectedWorkerCommandHex = Convert-RootHex $workerCommand 24576
    $script:rootState.SubmittedSha = Get-IntakeSha $submitted
    $script:rootState.Runtime = $runtime
    $script:rootState.SourceManifest = $source
    $script:rootState.ExpectedImageHex = Convert-RootHex $registration['runtime_contract']['path_spelling']['expected_queried_interpreter_image_literal'] 512
    if (-not $script:rootState.PureHost) { $script:rootState.Packet = Complete-RootCanonicalBody $submitted }
}

function Get-RootExpectedRuntimePins {
    $pins = [Collections.Generic.List[object]]::new()
    $pins.Add($script:rootState.Runtime['interpreter'])
    $sources = $script:rootState.SourceManifest['sources']
    foreach ($index in @(0, 1)) {
        $source = $sources[$index]
        $pins.Add([ordered]@{ role = $source['role']; path = $source['path']; byte_length = $source['raw_byte_length']; sha256 = $source['raw_sha256'] })
    }
    foreach ($pair in @(@('protocol', 'protocol'), @('declarations', 'oracle'))) {
        $reference = $script:rootState.Expectations[$pair[0]]
        $pins.Add([ordered]@{ role = $pair[1]; path = $reference['path']; byte_length = $reference['raw_byte_length']; sha256 = $reference['raw_sha256'] })
    }
    foreach ($index in @(2, 3, 4, 5)) {
        $source = $sources[$index]
        $pins.Add([ordered]@{ role = 'registered_dependency'; path = $source['path']; byte_length = $source['raw_byte_length']; sha256 = $source['raw_sha256'] })
    }
    foreach ($module in $script:rootState.Runtime['static_modules']) {
        $path = $script:rootUnicode.GetString([Convert]::FromHexString($module['absolute_path_utf16le_hex']))
        if ($path -ceq $script:rootState.Runtime['interpreter']['path']) { continue }
        $leaf = [IO.Path]::GetFileName($path)
        $role = switch -CaseSensitive ($leaf) {
            'kernel32.dll' { 'kernel32' }; 'KernelBase.dll' { 'kernelbase' }; 'ntdll.dll' { 'ntdll' }
            default { 'registered_dependency' }
        }
        $pins.Add([ordered]@{ role = $role; path = $path; byte_length = $module['byte_length']; sha256 = $module['sha256'] })
    }
    if ($pins.Count -ne 33) { Stop-RootObservation 'runtime_pin_count' }
    return ,$pins.ToArray()
}

function Assert-RootEntry {
    param([object]$Entry, [object]$Seal, [object]$SealReference)
    Assert-IntakeKeys $Entry @('version', 'case_id', 'expectations', 'launch_seal', 'wrapper', 'observer', 'authority_flags')
    if ($Entry['version'] -cne 'local-member-intake-bootstrap-observer-entry-v1' -or
        $Entry['case_id'] -cne $CaseId) { Stop-RootObservation 'entry_context' }
    Assert-RootEqual $Entry['expectations'] $Seal['expectations'] 'entry_expectations'
    Assert-RootEqual $Entry['launch_seal'] $SealReference 'entry_seal'
    Assert-RootEqual $Entry['authority_flags'] $script:rootState.Flags 'authority_flags'
    $null = Assert-RootRawReference $Entry['wrapper'] 262144
    Assert-IntakeKeys $Entry['observer'] @('pid', 'image_utf16le_hex', 'command_utf16le_hex', 'start_time', 'cim')
    Assert-RootInteger $Entry['observer']['pid'] 1 4294967295
    if ($null -eq $Entry['observer']['start_time'] -or $null -eq $Entry['observer']['cim']) { Stop-RootObservation 'entry_identity' }
    Assert-RootDateShape $Entry['observer']['start_time'] 1
    Assert-RootCompleteCimShape $Entry['observer']['cim'] 'observer' ([uint]$Entry['observer']['pid'])
}

function Initialize-RootObserver {
    param([object]$Entry)
    $null = Invoke-RootManaged 'Process.GetCurrentProcess' $null
    $id = Invoke-RootManaged 'Process.Id' (New-RootRef 'process' 0)
    $null = Invoke-RootManaged 'Process.Handle' (New-RootRef 'process' 0)
    $birth = Invoke-RootManaged 'Process.StartTime' (New-RootRef 'process' 0)
    $image = Invoke-RootManaged 'Process.MainModule.FileName' (New-RootRef 'process' 0)
    $command = Convert-RootHex ([Environment]::CommandLine) 32768
    $query = Invoke-RootCim 'observer' ([uint]$id.value)
    $observer = [ordered]@{ pid = $id.value; image_utf16le_hex = $image.value; command_utf16le_hex = $command; start_time = $birth.value; cim = $query }
    $script:rootState.Observer = $observer
    $expected = $Entry['observer']
    foreach ($name in @('pid', 'image_utf16le_hex', 'command_utf16le_hex')) {
        if ($observer[$name] -cne $expected[$name]) { Stop-RootObservation 'observer_entry_identity' }
    }
    if ($birth.value.conversion_state -cne 'valid' -or $expected['start_time']['conversion_state'] -cne 'valid' -or
        $birth.value.filetime_u64 -ne $expected['start_time']['filetime_u64'] -or
        $expected['cim']['state'] -cne 'complete' -or $expected['cim']['selected_instances'].Length -ne 1) {
        Stop-RootObservation 'observer_entry_birth'
    }
    $expectedNative = [ordered]@{
        pid = $id.value; creation_filetime_u64 = $birth.value.filetime_u64
        image_utf16le_hex = $image.value; command_utf16le_hex = $command
    }
    $parentId = [uint]$expected['cim']['selected_instances'][0]['parent_process_id']
    Assert-RootIdentity $expected['cim'] $expectedNative $parentId $birth.value
    Assert-RootIdentity $query $expectedNative $parentId $birth.value
}

function Start-RootHost {
    $hostInvocationRecord = $script:rootState.HostInvocation
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $hostInvocationRecord['file_name']; $startInfo.WorkingDirectory = $hostInvocationRecord['working_directory']
    $startInfo.UseShellExecute = $false; $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true; $startInfo.RedirectStandardOutput = $true; $startInfo.RedirectStandardError = $true
    foreach ($argument in $hostInvocationRecord['argument_list']) { $startInfo.ArgumentList.Add($argument) }
    $startInfo.Environment.Clear()
    foreach ($pair in $hostInvocationRecord['environment']) { $startInfo.Environment.Add($pair['name'], $pair['value']) }
    $process = [Diagnostics.Process]::new(); $process.StartInfo = $startInfo
    $script:rootState.Processes[1] = $process
    $record = [ordered]@{
        prepared = $true
        start_info = [ordered]@{
            file_name = $hostInvocationRecord['file_name']; argument_list = $hostInvocationRecord['argument_list']; working_directory = $hostInvocationRecord['working_directory']
            environment = $hostInvocationRecord['environment']; use_shell_execute = $false; create_no_window = $true
            redirect_stdin = $true; redirect_stdout = $true; redirect_stderr = $true
        }
        start_attempted = $false; start_return = $null; process_id = $null; process_handle_u64 = $null
        start_time = $null; main_module_path_utf16le_hex = $null; error = $null
    }
    $script:rootState.HostCreation = $record
    try {
        $started = Invoke-RootManaged 'Process.Start' (New-RootRef 'process' 1)
        $record.start_return = $started.value
        if ($started.value -cne $true) { Stop-RootObservation 'host_creation' }
        # Drain is submitted before blocking identity getters or CIM work.
        Start-RootRead 1; Start-RootRead 2
    }
    catch { $record.error = Convert-RootError $_; throw }
    foreach ($getter in @(
        @('Process.Id', 'process_id'), @('Process.Handle', 'process_handle_u64'),
        @('Process.StartTime', 'start_time'), @('Process.MainModule.FileName', 'main_module_path_utf16le_hex')
    )) {
        try { $value = Invoke-RootManaged $getter[0] (New-RootRef 'process' 1); $record[$getter[1]] = $value.value }
        catch {
            if ($null -eq $record.error) { $record.error = Convert-RootError $_ }
            if (-not $script:rootState.NoHandoff) { throw }
        }
    }
    if (-not $script:rootState.NoHandoff -and
        ($record.main_module_path_utf16le_hex -cne $script:rootState.ExpectedImageHex -or
        $null -eq $record.start_time -or $record.start_time.conversion_state -cne 'valid')) {
        Stop-RootObservation 'host_identity'
    }
}

function Update-RootFrames {
    $bytes = $script:rootState.StreamBytes[1].ToArray()
    if (-not $script:rootState.NoHandoff -and $null -eq $script:rootState.Request) {
        $request = Get-RootFrame $bytes 0 'LMR1' 262144
        if ($null -ne $request) { Start-RootAcknowledgement $request }
    }
    $offset = 0
    if ($null -ne $script:rootState.Request) {
        $offset = 8 + (Convert-IntakeCanonicalBytes $script:rootState.Request).Length
    }
    if (($script:rootState.NoHandoff -or $null -ne $script:rootState.Request) -and $null -eq $script:rootState.TerminalFrame) {
        $terminal = Get-RootFrame $bytes $offset 'LMF1' 67108864
        if ($null -ne $terminal) { $script:rootState.TerminalFrame = $terminal }
    }
}

function Receive-RootHost {
    while ($true) {
        Complete-RootRead 1 $true; Complete-RootRead 2 $true
        Complete-RootStdin
        Update-RootFrames
        $signalled = Wait-RootHost 0
        if ($signalled -and $script:rootState.Eof[1] -and $script:rootState.Eof[2] -and
            $null -eq $script:rootState.ActiveStdinTask) { break }
        $now = Get-RootClock
        if ($now -ge $script:rootState.Terminal.work_deadline_monotonic_ns) { Stop-RootObservation 'root_work_deadline' }
        if ($null -ne $script:rootState.ActiveStdinTask -and
            $now -ge $script:rootState.Terminal.ack_deadline_monotonic_ns) { Stop-RootObservation 'root_ack_deadline' }
        $remaining = [Numerics.BigInteger]$script:rootState.Terminal.work_deadline_monotonic_ns - $now
        $milliseconds = [int][Math]::Min(20, [decimal][Numerics.BigInteger]::Divide($remaining, 1000000))
        $null = Wait-RootHost $milliseconds
    }
}

function Close-RootHost {
    param([bool]$Failed)
    $script:rootState.CleanupPhase = $true
    if ($script:rootState.HostStarted) {
        $now = Get-RootClock
        $remaining = $script:rootHardEnd - $script:rootLastUtc
        if ($remaining -lt 0) { $remaining = 0 }
        $cleanupLimit = [Numerics.BigInteger]$now + [Numerics.BigInteger]::Min(3000000000, $remaining)
        $script:rootState.CleanupDeadline = $cleanupLimit
        if ($Failed -and $script:rootState.Terminal.host_signalled -cne $true) {
            try { $null = Invoke-RootManaged 'Process.Kill' (New-RootRef 'process' 1) @((New-RootValue 'bool' $false)) }
            catch { $script:rootState.CleanupFault = $true }
        }
        foreach ($streamId in @(1, 2)) {
            if (-not $script:rootState.Eof[$streamId] -and $null -eq $script:rootState.ActiveReads[$streamId]) {
                try { Start-RootRead $streamId } catch { $script:rootState.CleanupFault = $true }
            }
        }
        while ((Get-RootClock) -lt $cleanupLimit) {
            foreach ($streamId in @(1, 2)) {
                try { Complete-RootRead $streamId $true } catch { $script:rootState.CleanupFault = $true }
            }
            try { Complete-RootStdin } catch { $script:rootState.CleanupFault = $true; $script:rootState.ActiveStdinTask = $null }
            try { $null = Wait-RootHost 20 } catch { $script:rootState.CleanupFault = $true }
            if ($script:rootState.Terminal.host_signalled -ceq $true -and
                $script:rootState.Eof[1] -and $script:rootState.Eof[2] -and
                $null -eq $script:rootState.ActiveStdinTask) { break }
        }
        if ($script:rootState.Terminal.host_signalled -ceq $true) {
            try { $exit = Invoke-RootManaged 'Process.ExitCode' (New-RootRef 'process' 1); $script:rootState.Terminal.host_exit_code_i32 = $exit.value }
            catch { $script:rootState.CleanupFault = $true }
        }
        foreach ($id in @(0, 1, 2)) {
            try { Close-RootStream $id } catch { $script:rootState.CleanupFault = $true }
        }
        # Closing a stream does not establish EOF or completed Tasks. Retain those facts independently.
        foreach ($streamId in @(1, 2)) {
            try { Complete-RootRead $streamId $false } catch { $script:rootState.CleanupFault = $true }
        }
        if ($null -ne $script:rootState.ActiveStdinTask) {
            try { Complete-RootStdin } catch { $script:rootState.CleanupFault = $true }
        }
    }
    $allSettled = $true
    foreach ($task in $script:rootState.Tasks) { if (-not $task.settled) { $allSettled = $false } }
    $script:rootState.Terminal.all_pending_tasks_completed = $allSettled
    $disposed = $true
    foreach ($id in @(1, 0)) {
        if ($script:rootState.Processes.ContainsKey($id)) {
            try { $null = Invoke-RootManaged 'Process.Dispose' (New-RootRef 'process' $id) }
            catch { $disposed = $false; $script:rootState.CleanupFault = $true }
        }
    }
    $script:rootState.Terminal.process_disposed = $disposed
    $script:rootState.Terminal.cleanup_complete = $script:rootState.HostStarted -and
        $script:rootState.Terminal.host_signalled -ceq $true -and $allSettled -and
        $script:rootState.Eof[1] -and $script:rootState.Eof[2] -and
        $script:rootState.Closed[0] -and $script:rootState.Closed[1] -and $script:rootState.Closed[2] -and
        $disposed -and -not $script:rootState.CleanupFault
}

function Complete-RootReceipt {
    param([bool]$Failed)
    $stdout = $script:rootState.StreamBytes[1].ToArray()
    $stderr = $script:rootState.StreamBytes[2].ToArray()
    if ($script:rootState.HostStarted) {
        $null = Save-RootArtifact 'host_stdout' 'host_stdout.bin' $stdout $script:rootState.Eof[1] 'observed_stream_bytes' $stdout.Length
        $null = Save-RootArtifact 'host_stderr' 'host_stderr.bin' $stderr $script:rootState.Eof[2] 'observed_stream_bytes' $stderr.Length
    }
    if ($script:rootState.HostStarted -and $null -eq $script:rootState.PreparedArtifact) {
        $script:rootState.PreparedArtifact = Save-RootArtifact 'root_stdin' 'root_stdin_prepared.bin' ([byte[]]::new(0)) $true 'prepared_write_input' $null
    }
    $hostRange = $null
    if (-not $Failed) {
        Update-RootFrames
        $frame = $script:rootState.TerminalFrame
        if ($null -eq $frame -or $stdout.Length -ne $frame.offset + $frame.bytes.Length -or
            $stderr.Length -ne 0 -or $script:rootState.Terminal.host_exit_code_i32 -ne 0 -or
            $script:rootState.Terminal.cleanup_complete -cne $true) { Stop-RootObservation 'complete_delivery' }
        $hostReceipt = $frame.value
        Assert-IntakeKeys $hostReceipt @('version', 'case_id', 'packet', 'packet_sha256', 'registration_sha256', 'oracle_sha256', 'declared_policy', 'runtime_pins', 'parent_identity', 'creation', 'job_observations', 'api_trace', 'lifecycle', 'stdout', 'stderr', 'result', 'fault_observation', 'terminal', 'authority_flags', 'receipt_sha256')
        foreach ($name in @('version', 'case_id', 'packet_sha256', 'registration_sha256', 'oracle_sha256', 'receipt_sha256')) {
            if ($hostReceipt[$name] -isnot [string]) { Stop-RootObservation 'host_receipt_domain' }
        }
        if ($hostReceipt['version'] -cne 'local-member-intake-bootstrap-attempt-v3' -or $hostReceipt['case_id'] -cne $CaseId -or
            $hostReceipt['registration_sha256'] -cne $script:rootState.RegistrationSha -or
            $hostReceipt['oracle_sha256'] -cne $script:rootState.Expectations['declarations']['raw_sha256'] -or
            $hostReceipt['packet_sha256'] -cne $script:rootState.SubmittedSha -or
            $hostReceipt['terminal']['acceptance'] -cne 'accepted_control') { Stop-RootObservation 'host_receipt_context' }
        Assert-RootEqual $hostReceipt['authority_flags'] $script:rootState.Flags 'authority_flags'
        Assert-RootEqual $hostReceipt['runtime_pins'] (Get-RootExpectedRuntimePins) 'runtime_pin_context'
        Assert-RootOwnDigest $hostReceipt 'receipt_sha256'
        if ($script:rootState.NoHandoff) {
            if ($null -ne $script:rootState.Request -or $null -ne $script:rootState.Ack -or
                $script:rootState.Queries.Count -ne 1) { Stop-RootObservation 'no_handoff_branch' }
        }
        else {
            if ($null -eq $script:rootState.Request -or $null -eq $script:rootState.Ack -or
                $script:rootState.Ack['decision'] -cne 'allow' -or -not $script:rootState.WriteCompleted -or
                -not $script:rootState.FlushCompleted -or $script:rootState.Queries.Count -ne 3) {
                Stop-RootObservation 'incomplete_handoff'
            }
            $transport = $hostReceipt['creation']['identity_transport']
            Assert-RootEqual $transport['request'] $script:rootState.Request 'host_request_association'
            Assert-RootEqual $transport['ack'] $script:rootState.Ack 'host_ack_association'
            foreach ($index in $script:rootState.Frames) { if ($index.role -ceq 'ack') { $index.complete = $true } }
        }
        Add-RootFrameIndex 'terminal' 'host_stdout.bin' $frame $true
        $hostRange = [ordered]@{
            artifact_path = 'host_stdout.bin'; byte_offset = $frame.offset + 8; byte_length = $frame.body.Length
            sha256 = Get-IntakeSha $frame.body; parsed_receipt = $hostReceipt
        }
        $script:rootState.Terminal.outcome = 'complete'
        $script:rootState.Terminal.acceptance = 'accepted_control'
    }
    $script:rootState.Terminal.host_wait_calls = $script:rootState.Waits.ToArray()
    $script:rootState.Terminal.stream_closes = $script:rootState.Closes.ToArray()
    $script:rootState.Terminal.poll_observations = $script:rootState.Polls.ToArray()
    $script:rootState.Terminal.frame_index = $script:rootState.Frames.ToArray()
    $artifacts = [Collections.Generic.List[object]]::new()
    foreach ($artifact in $script:rootState.Artifacts) {
        if ($null -eq $artifact) {
            $script:rootState.Terminal.acceptance = 'incomplete'; $script:rootState.Terminal.outcome = 'incomplete'
        }
        else { $artifacts.Add($artifact) }
    }
    $receipt = [ordered]@{
        version = 'local-intake-root-observation-v1'; registration_sha256 = $script:rootState.RegistrationSha
        case_id = $CaseId; wrapper_sha256 = $ObserverSha256; observer = $script:rootState.Observer
        host_creation = $script:rootState.HostCreation; managed_calls = $script:rootState.Calls.ToArray()
        queries = $script:rootState.Queries.ToArray(); request = $script:rootState.Request; ack = $script:rootState.Ack
        host_receipt = $hostRange; artifacts = $artifacts.ToArray(); terminal = $script:rootState.Terminal
        authority_flags = $script:rootState.Flags
    }
    $metadataView = [ordered]@{}
    foreach ($key in $receipt.Keys) {
        if ($key -ceq 'host_receipt' -and $null -ne $hostRange) {
            $metadataView[$key] = [ordered]@{
                artifact_path = $hostRange.artifact_path; byte_offset = $hostRange.byte_offset
                byte_length = $hostRange.byte_length; sha256 = $hostRange.sha256; parsed_receipt = $null
            }
        }
        else { $metadataView[$key] = $receipt[$key] }
    }
    $metadataView['receipt_sha256'] = '0000000000000000000000000000000000000000000000000000000000000000'
    $metadataLength = (Convert-IntakeCanonicalBytes $metadataView).Length
    if ($metadataLength -gt 16777216) { Stop-RootObservation 'metadata_first_excess' }
    $receipt['receipt_sha256'] = Get-IntakeSha (Convert-IntakeCanonicalBytes $receipt)
    $bytes = Convert-IntakeCanonicalBytes $receipt
    if ($script:rootState.RawArtifactBytes + $bytes.Length -gt 335544320) { Stop-RootObservation 'aggregate_first_excess' }
    # The root body is sealed after host delivery/EOF/exit/task settlement, before its own persistence.
    $null = Get-RootClock
    $path = $script:rootState.Selected['outputs']['root_receipt']
    $output = [IO.FileStream]::new($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $output.Write($bytes, 0, $bytes.Length); $output.Flush($true) }
    finally { $output.Dispose() }
    try {
        $null = Get-RootClock
        if ($script:rootLastUtc -ge $script:rootHardEnd) { Stop-RootObservation 'deadline_after_persistence' }
    }
    catch {
        if ($null -ne $script:rootClockFailure) { Invoke-RootEmergencyCleanup $_ }
        throw
    }
    return ,$receipt
}

# Only the registered driver below performs actual observation. Functions are not dot-sourced elsewhere.
$earlyUtc = ([Numerics.BigInteger][DateTime]::UtcNow.Ticks - [DateTime]::UnixEpoch.Ticks) * 100
if ($earlyUtc -ge $script:rootHardEnd) { Stop-RootObservation 'deadline_or_clock' }
foreach ($sha in @($ExpectedExpectationsSha256, $ObserverSha256, $PrimitivesSha256)) {
    if ($sha -cnotmatch '\A[0-9a-f]{64}\z') { Stop-RootObservation 'invocation_pin' }
}
$fixedDirectory = 'C:/Users/pabta/Projects/ai-trader/scripts/'
$selfPath = $fixedDirectory + 'local_member_intake_bootstrap_observer_20261015_1.ps1'
$modulePath = $fixedDirectory + 'local_member_intake_bootstrap_primitives_20261015_1.psm1'
if ($PSCommandPath.Replace('\', '/') -cne $selfPath) { Stop-RootObservation 'observer_path' }
$selfBytes = Read-RootBoundedBody $selfPath 262144
$moduleBytes = Read-RootBoundedBody $modulePath 262144
if ((Get-RootRawSha $selfBytes) -cne $ObserverSha256 -or (Get-RootRawSha $moduleBytes) -cne $PrimitivesSha256) {
    Stop-RootObservation 'source_pin'
}
Import-Module -Name $modulePath -ErrorAction Stop
$sealBytes = Read-RootBoundedBody $LaunchSealPath 1048576
$seal = Complete-RootCanonicalBody $sealBytes
$sealReference = Get-RootRefForBody $LaunchSealPath $sealBytes $seal
if ($seal['expectations']['raw_sha256'] -cne $ExpectedExpectationsSha256) { Stop-RootObservation 'external_expectations_pin' }
Assert-RootEqual $seal['observer'] ([ordered]@{ path = $selfPath; raw_byte_length = $selfBytes.Length; raw_sha256 = $ObserverSha256 }) 'seal_observer'
Assert-RootEqual $seal['primitives'] ([ordered]@{ path = $modulePath; raw_byte_length = $moduleBytes.Length; raw_sha256 = $PrimitivesSha256 }) 'seal_primitives'
$expectationsCapture = Read-RootCanonicalArtifact $seal['expectations'] 4194304
$expectations = $expectationsCapture.value
$script:rootState = [ordered]@{
    Expectations = $expectations; Registration = $null; RegistrationSha = $null; Flags = @()
    Selected = $null; OutputDirectory = $null; Protocol = $null; Declarations = $null; Runtime = $null; SourceManifest = $null
    Observer = $null; HostCreation = $null; HostInvocation = $null; Packet = $null; ExpectedPacketSha = $null
    SubmittedSha = $null; ExpectedImageHex = $null; ExpectedWorkerCommandHex = $null
    Calls = [Collections.Generic.List[object]]::new(); Queries = [Collections.Generic.List[object]]::new()
    Artifacts = [Collections.Generic.List[object]]::new(); ArtifactNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    Polls = [Collections.Generic.List[object]]::new(); Waits = [Collections.Generic.List[object]]::new()
    Closes = [Collections.Generic.List[object]]::new(); Frames = [Collections.Generic.List[object]]::new()
    Processes = [Collections.Generic.Dictionary[int, object]]::new(); Streams = [Collections.Generic.Dictionary[int, object]]::new()
    ProcessDisposeAttempted = [Collections.Generic.HashSet[int]]::new()
    Buffers = [Collections.Generic.List[byte[]]]::new(); Tasks = [Collections.Generic.List[object]]::new()
    ReadOrdinalByBuffer = [Collections.Generic.Dictionary[int, int]]::new()
    ActiveReads = @{ 1 = $null; 2 = $null }; Eof = @{ 1 = $false; 2 = $false }
    Closed = @{ 0 = $false; 1 = $false; 2 = $false }; CloseAttempted = @{ 0 = $false; 1 = $false; 2 = $false }
    StreamLimits = @{ 1 = 67371024; 2 = 1048576 }
    StreamBytes = @{ 1 = [IO.MemoryStream]::new(); 2 = [IO.MemoryStream]::new() }
    Request = $null; Ack = $null; TerminalFrame = $null; PreparedArtifact = $null; ActiveStdinTask = $null
    ReadAttempts = 0; ReadBufferBytes = 0; RawArtifactBytes = [long]0
    WriteCompleted = $false; FlushCompleted = $false; HostStarted = $false; CleanupPhase = $false; CleanupFault = $false; CleanupDeadline = $null; KillAttempted = $false
    PureHost = $CaseId -cin @('packet_first_excess', 'packet_wrong_pin', 'unknown_control')
    NoHandoff = $CaseId -cin @('packet_first_excess', 'packet_wrong_pin', 'unknown_control', 'creation_refusal', 'suspended_identity_refusal', 'suspended_membership_refusal')
    Terminal = [ordered]@{
        outcome = 'incomplete'; work_deadline_monotonic_ns = $null; ack_deadline_monotonic_ns = $null
        host_signalled = $null; host_exit_code_i32 = $null; host_wait_calls = @(); stream_closes = @()
        process_disposed = $null; all_pending_tasks_completed = $null; cleanup_complete = $null
        acceptance = 'incomplete'; poll_observations = @(); frame_index = @()
    }
}
foreach ($ordinal in @(0, 1, 2)) { $script:rootState.Artifacts.Add($null) }
Assert-RootLaunchInputs $seal $expectations
$entryPath = [IO.Path]::Combine($script:rootState.OutputDirectory, 'observer_entry.json')
$entryBytes = Read-RootBoundedBody $entryPath 1048576
$entry = Complete-RootCanonicalBody $entryBytes
Assert-RootEntry $entry $seal $sealReference
$failed = $false
$observedFailure = $null
try {
    Initialize-RootObserver $entry
    Start-RootHost
    Receive-RootHost
}
catch {
    $failed = $true
    $observedFailure = $_
    $script:rootState.Terminal.outcome = if ($script:rootState.HostStarted) { 'transport_refusal' } else { 'preflight_refusal' }
}
finally {
    if ($null -eq $script:rootClockFailure) {
        try { Close-RootHost $failed }
        catch {
            $failed = $true
            if ($null -eq $observedFailure) { $observedFailure = $_ }
            if ($null -eq $script:rootClockFailure) { throw }
        }
    }
    if ($null -ne $script:rootClockFailure) {
        Invoke-RootEmergencyCleanup $observedFailure
    }
}
if ($null -ne $script:rootClockFailure) {
    # A clock-invalid action log is not a conforming positive RootObservationReceipt.
    throw $observedFailure
}
$completedReceipt = Complete-RootReceipt $failed
return ,$completedReceipt
