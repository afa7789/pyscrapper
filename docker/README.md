This is experimental. ( I have not tested )

"cross compilation" with docker for pyinstaller 

The docker file and this reame is to be used considering you are at root of the repo.

```
## WINDOWS
docker build -t marketroxo-win-builder -f docker/Dockerfile .
docker run --rm -v "$(pwd)/dist_windows:/app/dist" marketroxo-win-builder

## LINUX
docker build -t marketroxo-linux-builder -f docker/linux.Dockerfile .
docker run --rm -v "$(pwd)/dist_linux:/app/dist" marketroxo-linux-builder
```
