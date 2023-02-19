# mypiradio
Small but powerful python3 script for using Raspberry Pi or similar SBC as remote controlled media center.

The idea is to use simple remote control, i.e. infrared one, to play internet radio stations, files from mounted disk (SD, USB etc), or given streams from the web/LAN. No display is required and there is no support for it - just audio and remote control.

## Classes inside the script are:
* *radioplayer* - plays media. Uses VLC as backend.
* *remotesource*, *keyboardsource* - gives string codes to manipulate the player. The "keyboard" one is used for testing. The "remote" one utilizes LIRC.
* *pg_storage* - stores, reads and updates any settings, radio stations web addresses, etc. Postgres is used for historical reasons.
* *soyuz_site* - takes some URL prefix and gives URL of the stream to play. Use BeautifulSoap, pafy to parse the site.
* *streaming_sites* - map of sites like soyuz_site or similar.

## The main script features are:
* Plays, pauses, resumes or stops sound.
* Jumps to previous/next file or folder.
* Has special code to play an audio book. In that case stopping the playback saves current timestamp, and the script restores playback from saved timestamp every time.
* Supports several music folders each with one level of subfolders. So every family member can have his/her own set of albums and switch tracks and albums inside of this set only (It is handy to use "color" buttons for this).
* Is designed for listening to daily programs (podcasts) from site with given URL.
* Has special button hook for playing one stream with hardcoded URL. This can be used to stream some complicated sound data from "big" PC to SBC. Requires installing streaming server  (i.e. icecast) on PC.
* Can increase/decrease volume.

## Possible customizations:
* To use another storage instead of Postgres make your own "storage" class.
* To use another website with podcasts/programs make your own "site" class and implement parsing method(s).
* To use another input instead of LIRC make your own "source" class.

*Sample .lircrc file is attached.*

