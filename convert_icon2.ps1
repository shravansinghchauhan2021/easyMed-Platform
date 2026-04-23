Add-Type -AssemblyName System.Drawing
$path = 'C:\Users\shravan singh\telemedicine_gravity\MedConnectMobile\app\src\main\res\drawable\ic_launcher.png'
$img = [System.Drawing.Image]::FromFile($path)
$tmp = $path + '.tmp.png'
$img.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png)
$img.Dispose()
Remove-Item -Force $path
Rename-Item $tmp 'ic_launcher.png'
