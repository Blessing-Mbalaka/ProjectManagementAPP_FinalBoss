# Optional Azure Blob / Azurite media storage

Install requirements, then set `AZURE_CONNECTION_STRING` to your Azure Storage
or Azurite connection string and `AZURE_CONTAINER` to the media container name
(default: `media`). Create that container before uploading. For Azurite, use a
full connection string with its BlobEndpoint reachable from the app and browser.
Uploads use Blob storage when the connection string is present; otherwise they
use the local media directory. Existing local uploads are not migrated.
Blob URLs are signed for one hour; static assets continue to use WhiteNoise.
