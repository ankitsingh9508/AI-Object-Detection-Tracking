const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const screenshotBtn = document.getElementById("screenshotBtn");
const recordBtn = document.getElementById("recordBtn");

const cameraFeed = document.getElementById("cameraFeed");
const cameraPlaceholder = document.getElementById("cameraPlaceholder");

let isRecording = false;


// API request function
async function apiRequest(url) {
    try {
        const response = await fetch(url, {
            method: "POST"
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Request failed");
        }

        return data;

    } catch (error) {
        alert(error.message);
        return null;
    }
}


// Start Detection
startBtn.addEventListener("click", async () => {

    const data = await apiRequest("/api/start");

    if (data) {
        cameraPlaceholder.style.display = "none";
        cameraFeed.src = "/video_feed?t=" + Date.now();
        alert("Detection Started Successfully!");
    }

});


// Stop Detection
stopBtn.addEventListener("click", async () => {

    const data = await apiRequest("/api/stop");

    if (data) {
        isRecording = false;
        recordBtn.innerText = "● Record";
        cameraPlaceholder.style.display = "flex";
        alert("Detection Stopped!");
    }

});


// Screenshot
screenshotBtn.addEventListener("click", async () => {

    const data = await apiRequest("/api/screenshot");

    if (data) {
        alert("Screenshot saved successfully!");
    }

});


// Video Recording
recordBtn.addEventListener("click", async () => {

    const data = await apiRequest("/api/record");

    if (data) {

        isRecording = data.recording;

        recordBtn.innerText = isRecording
            ? "■ Stop Recording"
            : "● Record";

        alert(data.message);

    }

});


// Update dashboard statistics
async function updateDashboard() {

    try {

        const response = await fetch("/api/status");
        const data = await response.json();

        document.getElementById("fps").innerText = data.fps;

        const counts = data.objects || {};

        const total = Object.values(counts)
            .reduce((sum, count) => sum + count, 0);

        document.getElementById("totalObjects").innerText = total;

        document.getElementById("objectTypes").innerText =
            Object.keys(counts).length;

        document.getElementById("trackingStatus").innerText =
            data.detection ? "ON" : "OFF";

        const objectList = document.getElementById("objectList");

        if (Object.keys(counts).length === 0) {

            objectList.innerHTML =
                '<p class="empty-message">No objects detected yet.</p>';

        } else {

            objectList.innerHTML = Object.entries(counts)
                .map(([name, count]) => `
                    <div class="object-item">
                        <span>${name}</span>
                        <strong>${count}</strong>
                    </div>
                `)
                .join("");

        }

    } catch (error) {
        console.log("Dashboard update error:", error);
    }

}


// Update every second
setInterval(updateDashboard, 1000);

updateDashboard();
// =================================
// ANALYTICS DASHBOARD
// =================================

async function updateAnalytics() {

    try {
        const response = await fetch("/api/analytics");
        const data = await response.json();

        const history = data.history || [];

        document.getElementById("totalRecords").innerText =
            data.total_records;

        document.getElementById("latestDetection").innerText =
            history.length > 0
                ? history[history.length - 1].total
                : 0;

        document.getElementById("historyStatus").innerText =
            history.length > 0 ? "Active" : "Waiting";

        const historyList = document.getElementById("historyList");

        if (history.length === 0) {

            historyList.innerHTML =
                '<p class="empty-message">No detection history available.</p>';

            return;
        }

        historyList.innerHTML = [...history]
            .reverse()
            .map(item => `
                <div class="history-item">
                    <span>${item.time}</span>
                    <span>Objects: ${Object.entries(item.objects)
                        .map(([name, count]) => `${name}: ${count}`)
                        .join(", ")}</span>
                    <strong>${item.total}</strong>
                </div>
            `)
            .join("");

    } catch (error) {
        console.log("Analytics Error:", error);
    }
}


// Update analytics every 5 seconds
setInterval(updateAnalytics, 5000);

updateAnalytics();
// =================================
// LIVE DETECTION GRAPH
// =================================

let detectionChart = null;

function initializeDetectionChart() {

    const canvas = document.getElementById("detectionChart");

    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    detectionChart = new Chart(canvas, {
        type: "line",

        data: {
            labels: [],

            datasets: [{
                label: "Detected Objects",
                data: [],
                borderColor: "#35b8ff",
                backgroundColor: "rgba(53,184,255,0.15)",
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: "#7775ff"
            }]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,

            animation: {
                duration: 500
            },

            plugins: {
                legend: {
                    labels: {
                        color: "#ffffff"
                    }
                }
            },

            scales: {
                x: {
                    ticks: {
                        color: "#a5a5c7"
                    },
                    grid: {
                        color: "rgba(255,255,255,0.06)"
                    }
                },

                y: {
                    beginAtZero: true,
                    ticks: {
                        color: "#a5a5c7",
                        precision: 0
                    },
                    grid: {
                        color: "rgba(255,255,255,0.06)"
                    }
                }
            }
        }
    });
}


// Update graph with individual object counts
async function updateDetectionChart() {

    if (!detectionChart) return;

    try {
        const response = await fetch("/api/analytics");
        const data = await response.json();

        const history = data.history || [];

        const labels = history.map(item => item.time);

        // Find all detected object categories
        const objectNames = [
            ...new Set(
                history.flatMap(item =>
                    Object.keys(item.objects || {})
                )
            )
        ];

        const colors = [
            "#35b8ff",
            "#7775ff",
            "#00e5c3",
            "#ff9f43",
            "#ff5ca8",
            "#a3e635",
            "#facc15"
        ];

        const datasets = objectNames.map((name, index) => {

            const color = colors[index % colors.length];

            return {
                label: name.toUpperCase(),

                data: history.map(item =>
                    (item.objects || {})[name] || 0
                ),

                borderColor: color,
                backgroundColor: color + "20",
                fill: false,
                tension: 0.4,
                pointRadius: 4
            };

        });

        detectionChart.data.labels = labels;
        detectionChart.data.datasets = datasets;

        detectionChart.update();

    } catch (error) {
        console.log("Graph Update Error:", error);
    }
}


// Initialize graph
initializeDetectionChart();

// Refresh graph every 5 seconds
setInterval(updateDetectionChart, 5000);

updateDetectionChart();

// Object Detection Summary
async function updateSummary() {
    try {
        const response = await fetch("/api/summary");
        const data = await response.json();

        document.getElementById("summaryTotalObjects").innerText =
            data.total_objects;

        document.getElementById("summaryMostDetected").innerText =
            data.most_detected;

        document.getElementById("summaryUniqueTypes").innerText =
            data.unique_object_types;

        document.getElementById("summarySessions").innerText =
            data.total_sessions;

    } catch (error) {
        console.log("Summary Error:", error);
    }
}

updateSummary();
setInterval(updateSummary, 3000);

// Object Tracking History
async function updateTrackingHistory() {
    try {
        const response = await fetch("/api/tracking");
        const data = await response.json();

        document.getElementById("totalTracked").innerText =
            data.total_tracked;

        const tableBody = document.getElementById("trackingTableBody");

        if (data.tracked_objects.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="4">No tracked objects available.</td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = data.tracked_objects.map(item => `
            <tr>
                <td>#${item.id}</td>
                <td>${item.name}</td>
                <td>${item.first_seen}</td>
                <td>${item.last_seen}</td>
            </tr>
        `).join("");

    } catch (error) {
        console.log("Tracking History Error:", error);
    }
}

updateTrackingHistory();
setInterval(updateTrackingHistory, 2000);