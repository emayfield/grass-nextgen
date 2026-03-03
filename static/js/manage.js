/**
 * Grass - Video Manager
 * JavaScript for managing demo videos
 */

// =============================================================================
// State
// =============================================================================

let songs = [];
let selectedSong = null;
let searchResults = [];
let selectedVideos = new Set();

// =============================================================================
// Song List
// =============================================================================

async function loadSongs() {
    try {
        const response = await fetch('/api/songs');
        songs = await response.json();
        renderSongs(songs);
    } catch (err) {
        document.getElementById('songList').innerHTML =
            '<div class="no-songs">Could not load songs</div>';
    }
}

function renderSongs(songsToRender) {
    const container = document.getElementById('songList');

    if (!songsToRender || songsToRender.length === 0) {
        container.innerHTML = '<div class="no-songs">No songs found</div>';
        return;
    }

    // Group by type
    const grouped = {};
    for (const song of songsToRender) {
        const type = song.type || 'other';
        if (!grouped[type]) grouped[type] = [];
        grouped[type].push(song);
    }

    // Order: instrumental, vocal, other
    const typeOrder = ['instrumental', 'vocal', 'other'];
    const typeLabels = {
        'instrumental': 'Instrumentals',
        'vocal': 'Vocal Songs',
        'other': 'Other'
    };

    // Helper to count demos
    const getDemoCount = (song) => (song.demo?.length || 0) + (song.featured_demo?.length || 0);

    let html = '';
    for (const type of typeOrder) {
        if (!grouped[type]) continue;
        // Sort by demo count (fewest first), then alphabetically
        grouped[type].sort((a, b) => {
            const countDiff = getDemoCount(a) - getDemoCount(b);
            if (countDiff !== 0) return countDiff;
            return a.title.localeCompare(b.title);
        });
        html += `<div class="song-list-section">${typeLabels[type] || type}</div>`;
        for (const song of grouped[type]) {
            const isSelected = selectedSong && selectedSong.id === song.id;
            const demoCount = (song.demo?.length || 0) + (song.featured_demo?.length || 0);
            html += `
                <div class="song-item ${isSelected ? 'selected' : ''}"
                     data-song-id="${song.id}"
                     onclick="selectSong('${song.id}')">
                    <span class="song-title">${song.title}</span>
                    <span class="song-key">${song.key}</span>
                    ${demoCount > 0 ? `<span class="song-vocal">${demoCount} videos</span>` : ''}
                </div>
            `;
        }
    }

    container.innerHTML = html;
}

function filterSongs(query) {
    query = query.toLowerCase().trim();

    if (!query) {
        renderSongs(songs);
        return;
    }

    const filtered = songs.filter(song =>
        song.title.toLowerCase().includes(query)
    );

    renderSongs(filtered);
}

// =============================================================================
// Song Selection
// =============================================================================

function selectSong(songId) {
    selectedSong = songs.find(s => s.id === songId);

    if (!selectedSong) return;

    // Update sidebar selection
    document.querySelectorAll('.song-item').forEach(el => {
        el.classList.toggle('selected', el.dataset.songId === songId);
    });

    // Show manage content
    document.getElementById('noSongSelected').style.display = 'none';
    document.getElementById('manageContent').style.display = 'block';

    // Update header
    document.getElementById('manageSongTitle').textContent = selectedSong.title;
    document.getElementById('manageSongKey').textContent = selectedSong.key;

    // Pre-fill search query
    document.getElementById('searchQuery').value = `${selectedSong.title} bluegrass live`;

    // Render current demos
    renderCurrentDemos();

    // Clear search results
    searchResults = [];
    selectedVideos.clear();
    document.getElementById('searchResults').innerHTML = '';
    document.getElementById('addSelectedBtn').style.display = 'none';
}

// =============================================================================
// Current Demos
// =============================================================================

function renderCurrentDemos() {
    const container = document.getElementById('currentDemos');
    const demos = [
        ...(selectedSong.featured_demo || []).map(url => ({ url, featured: true })),
        ...(selectedSong.demo || []).map(url => ({ url, featured: false }))
    ];

    if (demos.length === 0) {
        container.innerHTML = '<p class="no-demos-msg">No demo videos yet</p>';
        return;
    }

    let html = '';
    for (const demo of demos) {
        const videoId = extractVideoId(demo.url);
        const thumbUrl = videoId ? `https://img.youtube.com/vi/${videoId}/mqdefault.jpg` : '';

        html += `
            <div class="demo-item">
                <img class="demo-thumb" src="${thumbUrl}" alt="">
                <div class="demo-info">
                    <div class="demo-title">${demo.featured ? '(Featured) ' : ''}${demo.url}</div>
                    <div class="demo-url">
                        <a href="${demo.url}" target="_blank">${demo.url}</a>
                    </div>
                </div>
                <button class="remove-btn" onclick="removeDemo('${demo.url}')">Remove</button>
            </div>
        `;
    }

    container.innerHTML = html;
}

function extractVideoId(url) {
    // Handle youtu.be/ID and youtube.com/watch?v=ID formats
    const match = url.match(/(?:youtu\.be\/|youtube\.com\/watch\?v=)([^&]+)/);
    return match ? match[1] : null;
}

async function removeDemo(videoUrl) {
    if (!selectedSong) return;

    try {
        const response = await fetch('/api/remove_demo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                song_id: selectedSong.id,
                video_url: videoUrl
            })
        });

        const data = await response.json();
        if (data.success) {
            // Update local state
            if (selectedSong.demo) {
                selectedSong.demo = selectedSong.demo.filter(u => u !== videoUrl);
            }
            if (selectedSong.featured_demo) {
                selectedSong.featured_demo = selectedSong.featured_demo.filter(u => u !== videoUrl);
            }
            renderCurrentDemos();
            renderSongs(songs); // Update video count in sidebar
        } else {
            alert('Error: ' + data.error);
        }
    } catch (err) {
        alert('Error removing video: ' + err.message);
    }
}

// =============================================================================
// YouTube Search
// =============================================================================

async function searchYouTube() {
    const query = document.getElementById('searchQuery').value.trim();
    if (!query) return;

    const btn = document.getElementById('searchBtn');
    const resultsContainer = document.getElementById('searchResults');

    btn.disabled = true;
    btn.textContent = 'Searching...';
    resultsContainer.innerHTML = '<p class="no-results">Searching YouTube...</p>';

    try {
        const response = await fetch('/api/search_youtube', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, limit: 12 })
        });

        const data = await response.json();

        if (data.success) {
            searchResults = data.videos;
            selectedVideos.clear();
            renderSearchResults();
        } else {
            resultsContainer.innerHTML = `<p class="no-results">Error: ${data.error}</p>`;
        }
    } catch (err) {
        resultsContainer.innerHTML = `<p class="no-results">Error: ${err.message}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Search';
    }
}

function renderSearchResults() {
    const container = document.getElementById('searchResults');

    if (searchResults.length === 0) {
        container.innerHTML = '<p class="no-results">No videos found</p>';
        document.getElementById('addSelectedBtn').style.display = 'none';
        return;
    }

    let html = '';
    for (const video of searchResults) {
        const isSelected = selectedVideos.has(video.url);
        html += `
            <div class="video-card ${isSelected ? 'selected' : ''}"
                 onclick="toggleVideoSelection('${video.url}')">
                <img class="thumb" src="${video.thumbnail}" alt="">
                <div class="card-body">
                    <div class="video-title">${escapeHtml(video.title)}</div>
                    <div class="video-channel">${escapeHtml(video.channel)}</div>
                    <div class="video-duration">${video.duration}</div>
                    <div class="checkbox-row">
                        <input type="checkbox" ${isSelected ? 'checked' : ''}
                               onclick="event.stopPropagation(); toggleVideoSelection('${video.url}')">
                        <label>Add to song</label>
                    </div>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
    updateAddButton();
}

function toggleVideoSelection(url) {
    if (selectedVideos.has(url)) {
        selectedVideos.delete(url);
    } else {
        selectedVideos.add(url);
    }
    renderSearchResults();
}

function updateAddButton() {
    const btn = document.getElementById('addSelectedBtn');
    if (selectedVideos.size > 0) {
        btn.style.display = 'block';
        btn.textContent = `Add ${selectedVideos.size} Selected Video${selectedVideos.size > 1 ? 's' : ''}`;
    } else {
        btn.style.display = 'none';
    }
}

async function addSelectedVideos() {
    if (!selectedSong || selectedVideos.size === 0) return;

    const btn = document.getElementById('addSelectedBtn');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    let successCount = 0;
    let errors = [];

    for (const url of selectedVideos) {
        try {
            const response = await fetch('/api/add_demo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    song_id: selectedSong.id,
                    video_url: url,
                    featured: false
                })
            });

            const data = await response.json();
            if (data.success) {
                successCount++;
                // Update local state
                if (!selectedSong.demo) selectedSong.demo = [];
                if (!selectedSong.demo.includes(url)) {
                    selectedSong.demo.push(url);
                }
            } else {
                errors.push(data.error);
            }
        } catch (err) {
            errors.push(err.message);
        }
    }

    // Clear selection
    selectedVideos.clear();
    renderSearchResults();
    renderCurrentDemos();
    renderSongs(songs); // Update video count in sidebar

    btn.disabled = false;

    if (errors.length > 0) {
        alert(`Added ${successCount} videos. Errors: ${errors.join(', ')}`);
    }
}

// =============================================================================
// Utilities
// =============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================================================
// Initialize
// =============================================================================

document.addEventListener('DOMContentLoaded', loadSongs);

// Allow Enter key to trigger search
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && document.activeElement.id === 'searchQuery') {
        searchYouTube();
    }
});
