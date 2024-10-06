const playerAPI = (() => {
    const audioPlayer = new Audio();
    const folderInput = document.getElementById('folderInput');
    const songList = document.getElementById('songList');
    const songNameDisplay = document.getElementById('songName');
    const songImage = document.getElementById('songImage');
    const lyricsContainer = document.getElementById('lyricsContainer');
    const playPauseButton = document.getElementById('playPauseButton');
    const progressBar = document.getElementById('progressBar');
    const progress = document.getElementById('progress');
    const volumeSlider = document.getElementById('volumeSlider');
    const Gitlinkopen = document.getElementById('GithublinkBu');
    const rotationImage = document.getElementById('rotationImage');
    const modeInputs = document.querySelectorAll('input[name="mode"]');
    const themeButton = document.getElementById('themeswitch');
    const player = document.getElementById('player');
    const control = document.getElementById('control');
    const volcontrol = document.getElementById('volcontrol');
    const themeset = document.getElementById('themeset');
    const radiobar = document.getElementById('radiobar');
    const radioNames = document.querySelectorAll('.radio-inputs .name');
    const fileInputBefore = document.styleSheets[0].rules || document.styleSheets[0].cssRules;
    const songListItems = document.querySelectorAll('.song-list li');
    const info = document.getElementById('info');
    const NextSongBut = document.getElementById('Next');
    const PrevSongBut = document.getElementById('Prev');

    let isPlaying = false;
    let playbackMode = 'loop';
    let currentSongIndex = 0;
    let songFiles = [];
    let imageFiles = {};
    let lyricsFiles = {};
    let theme = 'dark';

    folderInput.addEventListener('change', handleFolderChange);
    playPauseButton.addEventListener('click', togglePlayPause);
    progressBar.addEventListener('click', seek);
    volumeSlider.addEventListener('input', changeVolume);
    audioPlayer.addEventListener('timeupdate', updateProgress);
    audioPlayer.addEventListener('ended', handleSongEnd);
    Gitlinkopen.addEventListener('click', openGitlink);
    modeInputs.forEach(input => input.addEventListener('change', changePlaybackMode));
    themeButton.addEventListener('click', toggleTheme);
    NextSongBut.addEventListener('click',NextSong);
    PrevSongBut.addEventListener('click',PreviousSong);
    modeInputs.forEach(input => {
        input.addEventListener('change', () => updateRadioStyles(
            theme === 'light' ? '#c4c4c4' : '#282828',
            theme === 'light' ? '#b3b3b3' : '#383838',
            theme === 'light' ? '#000' : '#fff'
        ));
    });


    function updateSongListHover(hoverColor) {
        const songListItems = document.querySelectorAll('.song-list li');
        songListItems.forEach(item => {
            item.addEventListener('mouseover', () => {
                item.style.backgroundColor = hoverColor;
            });
            item.addEventListener('mouseout', () => {
                item.style.backgroundColor = '';
            });
        });
    }

    function toggleTheme() {
        if (theme === 'dark') {
            theme = 'light';
            themeButton.textContent = '⚫️';
            document.body.style.backgroundColor = '#fff';
            document.body.style.color = '#000';
            player.style.backgroundColor = 'rgba(202, 202, 202, 0.8)';
            info.style.backgroundColor = 'rgba(202, 202, 202, 0.8)';
            control.style.backgroundColor = '#c4c4c4';
            volcontrol.style.backgroundColor = '#c4c4c4';
            themeset.style.backgroundColor = '#c4c4c4';
            radiobar.style.backgroundColor = '#c4c4c4';
            lyricsContainer.style.backgroundColor = '#c4c4c4';
            songList.style.backgroundColor = '#c4c4c4';
            folderInput.style.backgroundColor = '#c4c4c4';
            folderInput.style.color = '#000';
            
            updateRadioStyles('#c4c4c4', '#b3b3b3', '#000');
            updateFileInputStyle('#b3b3b3', '#739fda');
            updateSongListHover('#b3b3b3'); 
        } else {
            theme = 'dark';
            themeButton.textContent = '⚪️';
            document.body.style.backgroundColor = 'rgba(24, 24, 24, 0.9)';
            document.body.style.color = '#fff';
            player.style.backgroundColor = 'rgba(24, 24, 24, 0.9)';
            info.style.backgroundColor = 'rgba(24, 24, 24, 0.9)';
            control.style.backgroundColor = '#282828';
            volcontrol.style.backgroundColor = '#282828';
            themeset.style.backgroundColor = '#282828';
            radiobar.style.backgroundColor = '#282828';
            lyricsContainer.style.backgroundColor = '#282828';
            songList.style.backgroundColor = '#282828';
            folderInput.style.backgroundColor = '#282828';
            folderInput.style.color = '#fff';

            updateRadioStyles('#282828', '#383838', '#fff');
            updateFileInputStyle('#383838', '#739fda');
            updateSongListHover('#333'); // Update hover color for dark theme
        }
    }
    function updateRadioStyles(otherColor, selectedColor, textColor) {
        
        radioNames.forEach(name => {
            const input = name.previousElementSibling;
            if (input.checked) {
                name.style.backgroundColor = selectedColor;
            } else {
                name.style.backgroundColor = otherColor;
            }
            name.style.color = textColor;
        });
    }

    function updateFileInputStyle(bgColor, hoverColor) {
        
        for (let i = 0; i < fileInputBefore.length; i++) {
            if (fileInputBefore[i].selectorText === "input[type=\"file\"]::before") {
                fileInputBefore[i].style.backgroundColor = bgColor;
            }
            if (fileInputBefore[i].selectorText === "input[type=\"file\"]:hover::before") {
                fileInputBefore[i].style.backgroundColor = hoverColor;
            }
        }
    }



    function handleFolderChange(event) {
        const files = Array.from(event.target.files);
        songFiles = files.filter(file => file.type.startsWith('audio/'));

        imageFiles = files.reduce((acc, file) => {
            if (file.type.startsWith('image/')) {
                const baseName = getBaseName(file.name);
                acc[baseName] = file;
            }
            return acc;
        }, {});

        lyricsFiles = files.reduce((acc, file) => {
            if (file.name.endsWith('.lrc')) {
                const baseName = getBaseName(file.name);
                acc[baseName] = file;
            }
            return acc;
        }, {});

        songList.innerHTML = '';
        songFiles.forEach((song, index) => {
            const li = document.createElement('li');
            li.textContent = getBaseName(song.name);
            li.addEventListener('click', () => playSong(index));
            songList.appendChild(li);
        });

        folderInput.style.display = 'none';
    }
    
    function openGitlink() {
        window.open("https://github.com/ARRRsunny/music-player");
    }
    
    function playSong(index) {
        currentSongIndex = index;
        const song = songFiles[index];
        const songURL = URL.createObjectURL(song);
        audioPlayer.src = songURL;
        audioPlayer.play();
        isPlaying = true;
        updatePlayPauseButton();

        const baseName = getBaseName(song.name);
        songNameDisplay.textContent = baseName;

        loadImageAndLyrics(baseName);
        rotationImage.style.animationPlayState = 'running';
    }

    function loadImageAndLyrics(baseName) {
        if (imageFiles[baseName]) {
            const imageURL = URL.createObjectURL(imageFiles[baseName]);
            songImage.src = imageURL;
        } else {
            songImage.src = "https://raw.githubusercontent.com/ARRRsunny/music-player/main/assets/defapic.png";
        }

        if (lyricsFiles[baseName]) {
            const reader = new FileReader();
            reader.onload = (e) => displayLyrics(parseLRC(e.target.result));
            reader.readAsText(lyricsFiles[baseName]);
        } else {
            lyricsContainer.textContent = "No lyrics found.";
        }
    }

    function parseLRC(lrcText) {
        const lines = lrcText.split('\n');
        return lines.map(line => {
            const match = line.match(/\[(\d+):(\d+\.\d+)\](.+)/);
            if (match) {
                const minutes = parseInt(match[1], 10);
                const seconds = parseFloat(match[2]);
                const time = minutes * 60 + seconds;
                const text = match[3];
                return { time, text };
            }
        }).filter(Boolean);
    }

    function displayLyrics(lyrics) {
        if (lyrics.length === 0) {
            lyricsContainer.textContent = "No lyrics found.";
            return;
        }

        lyricsContainer.innerHTML = '';
        lyrics.forEach(({ time, text }) => {
            const p = document.createElement('p');
            p.setAttribute('data-time', time);
            p.textContent = text;
            lyricsContainer.appendChild(p);
        });

        audioPlayer.addEventListener('timeupdate', () => syncLyrics(lyrics));
    }

    function syncLyrics(lyrics) {
        const currentTime = audioPlayer.currentTime;
        const lines = lyricsContainer.querySelectorAll('p');
        lines.forEach((line, index) => {
            const lineTime = parseFloat(line.getAttribute('data-time'));
            if (currentTime >= lineTime) {
                lines.forEach(l => l.classList.remove('highlight'));
                line.classList.add('highlight');

                const lineHeight = line.offsetHeight;
                const containerHeight = lyricsContainer.clientHeight;
                const lineOffset = line.offsetTop;
                const nextLineTime = index < lines.length - 1 ? parseFloat(lines[index + 1].getAttribute('data-time')) : Infinity;
                
                if (currentTime < nextLineTime) {
                    const scrollPosition = lineOffset - containerHeight / 2 + lineHeight / 2 - 200;
                    lyricsContainer.scrollTo({
                        top: scrollPosition,
                        behavior: 'auto'
                    });
                }
            }
        });
    }

    function togglePlayPause() {
        if (isPlaying) {
            audioPlayer.pause();
            rotationImage.style.animationPlayState = 'paused';
        } else {
            audioPlayer.play();
            rotationImage.style.animationPlayState = 'running';
        }
        isPlaying = !isPlaying;
        updatePlayPauseButton();
    }

    function updatePlayPauseButton() {
        playPauseButton.textContent = isPlaying ? '⏸️' : '▶️';
    }

    function updateProgress() {
        const progressPercent = (audioPlayer.currentTime / audioPlayer.duration) * 100;
        progress.style.width = `${progressPercent}%`;
    }

    function seek(e) {
        const width = progressBar.clientWidth;
        const clickX = e.offsetX;
        const duration = audioPlayer.duration;
        audioPlayer.currentTime = (clickX / width) * duration;
    }

    function changeVolume() {
        audioPlayer.volume = volumeSlider.value;
    }

    function getBaseName(filename) {
        return filename.split('.').slice(0, -1).join('.');
    }

    function handleSongEnd() {
        switch (playbackMode) {
            case 'loop':
                playSong(currentSongIndex);
                break;
            case 'random':
                playSong(Math.floor(Math.random() * songFiles.length));
                break;
            case 'once':
                isPlaying = false;
                updatePlayPauseButton();
                rotationImage.style.animationPlayState = 'paused';
                break;
        }
    }
    
    function NextSong() {
        playSong(currentSongIndex+1);
    }
    
    function PreviousSong() {
        playSong(currentSongIndex-1);
    }


    function changePlaybackMode() {
        playbackMode = document.querySelector('input[name="mode"]:checked').value;
    }

    return {
        playSong,
        loadImageAndLyrics
    };
})();