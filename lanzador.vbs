' Ejecuta iniciar_app.bat sin ventana de consola (lo usa el acceso directo del Escritorio)
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
carpeta = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = carpeta
sh.Run "cmd /c """ & carpeta & "\iniciar_app.bat""", 0, False
