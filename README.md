# RekordboxFlacToMp3
Simple script to convert FLAC files to 320 kb/s MP3 while maintaining their Rekordbox metadata

## Usage

+ export your Rekordbox library to XML
+ install ffmpeg
+ clone this repository
+ run the script with `python rekordboxFLAC2MP3.py -i REKORDBOX_EXPORT_XML -o NEW_XML`
  - you can choose a particular playlist to copy by providing its name with `-p "your playlist name"`
+ in Rekordbox:
  + enable XML viewer mode if you haven't already; ensure that Settings -> View -> Layout -> "rekordbox xml" is checked
  + in Settings -> Advanced -> "rekordbox xml" -> "Imported Library", set this to the path of the XML file that was created by the script above
  + there is now a top-level folder in the browser called "rekordbox xml"
  + choose the list(s) you wanna import, right click, click import
  + you'll need to move the list in the playlist browser to just under where it appeared in the playlists
  + transfer the playlist to any USBs you might need
