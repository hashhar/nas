[BitTorrent]
Session\Port=${QBITTORRENT_LISTENING_PORT}
Session\Preallocation=true

; Seeding
Session\GlobalMaxRatio=2
Session\GlobalMaxSeedingMinutes=10080
Session\GlobalMaxInactiveSeedingMinutes=10080
Session\ShareLimitAction=Stop

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
PortForwardingEnabled=true

[Preferences]
Advanced\RecheckOnCompletion=true
General\Locale=en
General\StatusbarExternalIPDisplayed=true

; Web UI
WebUI\Enabled=true
WebUI\Address=*
WebUI\ServerDomains=*
WebUI\AuthSubnetWhitelistEnabled=true
WebUI\AuthSubnetWhitelist=192.168.0.0/22
WebUI\Username=${QBITTORRENT_WEBUI_USERNAME}
WebUI\Password_PBKDF2="${QBITTORRENT_WEBUI_PASSWORD}"
WebUI\UseUPnP=true

; Connection
Connection\PortRangeMin=${QBITTORRENT_LISTENING_PORT}
Connection\UPnP=true
