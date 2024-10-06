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
    let lyricsData = [];

    folderInput.addEventListener('change', handleFolderChange);
    playPauseButton.addEventListener('click', togglePlayPause);
    progressBar.addEventListener('click', seek);
    volumeSlider.addEventListener('input', changeVolume);
    audioPlayer.addEventListener('timeupdate', updateProgress);
    audioPlayer.addEventListener('ended', handleSongEnd);
    Gitlinkopen.addEventListener('click', openGitlink);
    modeInputs.forEach(input => input.addEventListener('change', changePlaybackMode));
    themeButton.addEventListener('click', toggleTheme);
    NextSongBut.addEventListener('click', NextSong);
    PrevSongBut.addEventListener('click', PreviousSong);
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
            updateSongListHover('#333');
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
            songImage.src = 'https://raw.githubusercontent.com/ARRRsunny/music-player/main/assets/defapic.png';
        }
        if (lyricsFiles[baseName]) {
            const reader = new FileReader();
            reader.onload = function (event) {
                parseLyrics(event.target.result);
            };
            reader.readAsText(lyricsFiles[baseName]);
        } else {
            lyricsContainer.textContent = 'Lyrics will appear here...';
            lyricsData = [];
        }
    }

    function parseLyrics(lrcText) {
        lyricsData = lrcText.split('\n').map(line => {
            const match = line.match(/\[(\d+):(\d+\.\d+)\](.*)/);
            if (match) {
                const minutes = parseInt(match[1], 10);
                const seconds = parseFloat(match[2]);
                const text = match[3].trim();
                const time = minutes * 60 + seconds;
                return { time, text };
            }
        }).filter(Boolean);
    
        lyricsContainer.innerHTML = lyricsData.map(lyric => `<p>${lyric.text}</p>`).join('');
    
    }

    function updateLyricsDisplay(currentTime) {
        const currentLyricIndex = lyricsData.findIndex((lyric, index) => {
            const nextLyric = lyricsData[index + 1];
            return currentTime >= lyric.time && (!nextLyric || currentTime < nextLyric.time);
        });
    
        if (currentLyricIndex !== -1) {
            const lyricElements = lyricsContainer.getElementsByTagName('p');
            Array.from(lyricElements).forEach((element, index) => {
                element.classList.toggle('highlight', index === currentLyricIndex);
            });
    
            // Scroll to the current lyric
            lyricElements[currentLyricIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
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

    function seek(event) {
        const width = progressBar.clientWidth;
        const clickX = event.offsetX;
        const duration = audioPlayer.duration;

        audioPlayer.currentTime = (clickX / width) * duration;
    }

    function updateProgress() {
        const { currentTime, duration } = audioPlayer;
        const progressPercent = (currentTime / duration) * 100;
        progress.style.width = `${progressPercent}%`;

        updateLyricsDisplay(currentTime);
    }

    function changeVolume() {
        audioPlayer.volume = volumeSlider.value;
    }

    function handleSongEnd() {
        if (playbackMode === 'loop') {
            playSong(currentSongIndex);
        } else if (playbackMode === 'random') {
            const randomIndex = Math.floor(Math.random() * songFiles.length);
            playSong(randomIndex);
        } else if (playbackMode === 'once') {
            audioPlayer.pause();
            isPlaying = false;
            updatePlayPauseButton();
            rotationImage.style.animationPlayState = 'paused';
        }
    }

    function changePlaybackMode(event) {
        playbackMode = event.target.value;
    }

    function NextSong() {
        currentSongIndex = (currentSongIndex + 1) % songFiles.length;
        playSong(currentSongIndex);
    }

    function PreviousSong() {
        currentSongIndex = (currentSongIndex - 1 + songFiles.length) % songFiles.length;
        playSong(currentSongIndex);
    }

    function getBaseName(fileName) {
        return fileName.substring(0, fileName.lastIndexOf('.'));
    }

    return {};
})();