param([Parameter(Mandatory=$true)][string]$LiteralPath, [switch]$Directory)
$ErrorActionPreference = 'Stop'
$mathmodelItem = Get-Item -LiteralPath $LiteralPath -Force
if ($mathmodelItem.PSIsContainer -ne [bool]$Directory -or ($mathmodelItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
    throw 'Credential storage has an invalid type.'
}
$mathmodelOwner = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$mathmodelAcl = Get-Acl -LiteralPath $LiteralPath
if ($mathmodelAcl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $mathmodelOwner.Value) {
    throw 'Credential storage must belong to the current user.'
}
$mathmodelAcl.SetAccessRuleProtection($true, $false)
foreach ($mathmodelRule in $mathmodelAcl.GetAccessRules($true, $false, [System.Security.Principal.SecurityIdentifier])) {
    $mathmodelAcl.RemoveAccessRuleSpecific($mathmodelRule)
}
if ($Directory) {
    $mathmodelAcl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new(
        $mathmodelOwner, [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit',
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow))
    [System.IO.Directory]::SetAccessControl($LiteralPath, $mathmodelAcl)
} else {
    $mathmodelAcl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new(
        $mathmodelOwner, [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow))
    [System.IO.File]::SetAccessControl($LiteralPath, $mathmodelAcl)
}
$mathmodelApplied = Get-Acl -LiteralPath $LiteralPath
$mathmodelRules = @($mathmodelApplied.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
if (-not $mathmodelApplied.AreAccessRulesProtected -or
    $mathmodelApplied.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $mathmodelOwner.Value -or
    $mathmodelRules.Count -ne 1 -or $mathmodelRules[0].IdentityReference.Value -ne $mathmodelOwner.Value -or
    $mathmodelRules[0].AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
    $mathmodelRules[0].FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl) {
    throw 'Unable to verify private credential permissions.'
}
if ($Directory -and $mathmodelRules[0].InheritanceFlags -ne [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit') {
    throw 'Unable to verify private credential inheritance.'
}
