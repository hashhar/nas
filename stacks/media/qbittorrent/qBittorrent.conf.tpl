[BitTorrent]
; Placeholder only. gluetun overwrites this via the WebUI API with the port
; ProtonVPN forwards over NAT-PMP, which changes on every reconnect.
Session\Port=${QBITTORRENT_LISTENING_PORT}
Session\UseRandomPort=false
Session\Preallocation=true

; Bind to gluetun's VPN interface. gluetun's firewall is the actual kill
; switch; this is the second layer — bound to tun0, qbittorrent stops rather
; than retrying against a blocked route while the tunnel is down or
; reconnecting.
Session\Interface=tun0
Session\InterfaceName=tun0

; Seeding
Session\GlobalMaxRatio=2
Session\GlobalMaxSeedingMinutes=10080
Session\GlobalMaxInactiveSeedingMinutes=10080
Session\ShareLimitAction=Stop

; Bandwidth, in KiB/s. 0 would be unlimited.
Session\GlobalUPSpeedLimit=500

; Do not change to manual mode, relocate torrents when paths or categories change
Session\DisableAutoTMMByDefault=false
Session\DisableAutoTMMTriggers\CategorySavePathChanged=false
Session\DisableAutoTMMTriggers\DefaultSavePathChanged=false

; Paths and layout
Session\SubcategoriesEnabled=true
Session\TorrentContentLayout=Subfolder
Session\TempPathEnabled=true
Session\TempPath=${TORRENT_ROOT}/Torrents/temp/
Session\DefaultSavePath=${TORRENT_ROOT}/Torrents/
Session\FinishedTorrentExportDirectory=${TORRENT_ROOT}/_torrents/Completed/

; Queuing
Session\AddTorrentStopped=true
Session\TorrentStopCondition=MetadataReceived
Session\AddTrackersEnabled=true
Session\AdditionalTrackers=${ADDITIONAL_TRACKERS}
Session\QueueingSystemEnabled=true
; default values
Session\MaxActiveTorrents=50
Session\MaxActiveDownloads=25
Session\MaxActiveUploads=25
; ignore slow torrents as defined below from queue limits
Session\IgnoreSlowTorrentsForQueueing=true
; in KiB/s
Session\SlowTorrentsDownloadRate=2
Session\SlowTorrentsUploadRate=2
; in seconds
Session\SlowTorrentsInactivityTimer=60
Session\PerformanceWarning=true

[Core]
AutoDeleteAddedTorrentFile=Never

[LegalNotice]
Accepted=true

[Network]
; UPnP/NAT-PMP is done by gluetun against the ProtonVPN gateway, not by
; qbittorrent against the LAN router (which is useless behind CGNAT anyway).
PortForwardingEnabled=false

[Preferences]
Advanced\RecheckOnCompletion=true
General\Locale=en
General\StatusbarExternalIPDisplayed=true

; Web UI
WebUI\Enabled=true
WebUI\Address=*
WebUI\ServerDomains=*
WebUI\Username=${QBITTORRENT_WEBUI_USERNAME}
WebUI\Password_PBKDF2="${QBITTORRENT_WEBUI_PASSWORD}"
WebUI\UseUPnP=false
; gluetun shares this network namespace and pushes the forwarded port over the
; WebUI API from 127.0.0.1, so it needs to skip authentication.
WebUI\LocalHostAuth=false

; Connection
Connection\PortRangeMin=${QBITTORRENT_LISTENING_PORT}
Connection\UPnP=false
