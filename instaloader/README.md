# Usage

* On NAS:

    ```sh
    DOCKER_DATA='/volume1/docker/appdata'
    mkdir $DOCKER_DATA/instaloader
    sudo chown -R syncthing:service_rw $DOCKER_DATA/instaloader
    ```

* On host:

    ```sh
    FIREFOX_PROFILES=/path/to/Firefox/Profiles/PROFILE_NAME
    scp $FIREFOX_PROFILES/cookies.sqlite nas:~/instaloder
    ```

* On NAS:

    ```sh
    mv ~/instaloader/cookies.sqlite $DOCKER_DATA/instaloder/cookies.sqlite
    USERNAME=<instgram_username>
    sudo docker-compose run --entrypoint /import_firefox_session.py -v $DOCKER_DATA/instaloader:/data instaloader -c /data/cookies.sqlite -f /data/.config/instaloader/session-$USERNAME
    sudo docker-compose run instaloader --login $USERNAME @$USERNAME
    ```
