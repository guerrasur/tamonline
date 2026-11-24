# Crea el acceso directo "Tamo online" en el Escritorio (el "?" no es válido en nombres de archivo)
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$escritorio = [Environment]::GetFolderPath('Desktop')
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $escritorio 'Tamo online.lnk'))
$lnk.TargetPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
$lnk.Arguments = '"' + (Join-Path $raiz 'lanzador.vbs') + '"'
$lnk.WorkingDirectory = $raiz
$lnk.IconLocation = (Join-Path $raiz 'assets\icono.ico') + ',0'
$lnk.WindowStyle = 7
$lnk.Description = 'Tamo online? - monitor de tiendas'
$lnk.Save()
Write-Host 'Acceso directo creado en el Escritorio.'
