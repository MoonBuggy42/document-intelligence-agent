/**
 * SynthetixAI Research Suite Frontend Logic
 * Supports Research Report Generation & LaTeX Math Paper Generation
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements - Navigation & Status
    const tabResearch = document.getElementById('tab-research');
    const tabMath = document.getElementById('tab-math');
    const researchPanel = document.getElementById('research-panel');
    const mathPanel = document.getElementById('math-panel');
    const backendStatus = document.getElementById('backendStatus');
    const statusLabel = backendStatus.querySelector('.status-label');

    // DOM Elements - Research
    const researchForm = document.getElementById('researchForm');
    const researchQuery = document.getElementById('researchQuery');
    const generateResearchBtn = document.getElementById('generateResearchBtn');
    const researchLoading = document.getElementById('researchLoading');
    const researchProgressText = document.getElementById('researchProgressText');
    const researchTimer = document.getElementById('researchTimer');
    const researchResult = document.getElementById('researchResult');
    const researchResultTopic = document.getElementById('researchResultTopic');
    const researchResultSummary = document.getElementById('researchResultSummary');
    const researchSourcesContainer = document.getElementById('researchSourcesContainer');
    const researchSourcesList = document.getElementById('researchSourcesList');
    const researchDownloadBtn = document.getElementById('researchDownloadBtn');

    // DOM Elements - Math
    const mathForm = document.getElementById('mathForm');
    const mathTopic = document.getElementById('mathTopic');
    const mathYearLevel = document.getElementById('mathYearLevel');
    const mathDifficulty = document.getElementById('mathDifficulty');
    const mathCount = document.getElementById('mathCount');
    const mathCountDisplay = document.getElementById('mathCountDisplay');
    const mathIncludeDiagrams = document.getElementById('mathIncludeDiagrams');
    const generateMathBtn = document.getElementById('generateMathBtn');
    const mathLoading = document.getElementById('mathLoading');
    const mathProgressText = document.getElementById('mathProgressText');
    const mathTimer = document.getElementById('mathTimer');
    const mathResult = document.getElementById('mathResult');
    const mathResultTitle = document.getElementById('mathResultTitle');
    const mathResultSubtitle = document.getElementById('mathResultSubtitle');
    const mathWorksheetDownloadBtn = document.getElementById('mathWorksheetDownloadBtn');
    const mathAnswersDownloadBtn = document.getElementById('mathAnswersDownloadBtn');

    // Active polling and timer references
    let researchPollInterval = null;
    let researchTimerInterval = null;
    let researchStartTime = null;

    let mathPollInterval = null;
    let mathTimerInterval = null;
    let mathStartTime = null;

    // ==========================================================================
    // 1. Tab Switching Logic
    // ==========================================================================
    function switchTab(target) {
        if (target === 'research') {
            tabResearch.classList.add('active');
            tabResearch.setAttribute('aria-selected', 'true');
            tabMath.classList.remove('active');
            tabMath.setAttribute('aria-selected', 'false');

            researchPanel.classList.add('active');
            mathPanel.classList.remove('active');
        } else {
            tabMath.classList.add('active');
            tabMath.setAttribute('aria-selected', 'true');
            tabResearch.classList.remove('active');
            tabResearch.setAttribute('aria-selected', 'false');

            mathPanel.classList.add('active');
            researchPanel.classList.remove('active');
        }
    }

    tabResearch.addEventListener('click', () => switchTab('research'));
    tabMath.addEventListener('click', () => switchTab('math'));

    // ==========================================================================
    // 2. Chips / Presets Logic
    // ==========================================================================
    document.querySelectorAll('.chip-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            researchQuery.value = btn.getAttribute('data-query');
            researchQuery.focus();
        });
    });

    document.querySelectorAll('.math-chip-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            mathTopic.value = btn.getAttribute('data-topic');
            mathYearLevel.value = btn.getAttribute('data-year');
            mathDifficulty.value = btn.getAttribute('data-difficulty');
            mathTopic.focus();
        });
    });

    // Math count slider display updater
    if (mathCount && mathCountDisplay) {
        mathCount.addEventListener('input', (e) => {
            mathCountDisplay.textContent = `${e.target.value} problems`;
        });
    }

    // ==========================================================================
    // 3. Backend Health Status Check
    // ==========================================================================
    async function checkBackendStatus() {
        try {
            const resp = await fetch('/api/status', { method: 'GET' });
            if (resp.ok) {
                const data = await resp.json();
                backendStatus.classList.remove('error');
                backendStatus.classList.add('connected');
                statusLabel.textContent = data.api_key_configured ? 'Mistral Online' : 'API Key Missing';
            } else {
                throw new Error('Status code ' + resp.status);
            }
        } catch (err) {
            backendStatus.classList.remove('connected');
            backendStatus.classList.add('error');
            statusLabel.textContent = 'Backend Offline';
        }
    }

    checkBackendStatus();
    setInterval(checkBackendStatus, 15000); // Check status every 15s

    // ==========================================================================
    // 4. Timer Helpers
    // ==========================================================================
    function formatTime(totalSeconds) {
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    function startTimer(timerEl, startTimeRef) {
        const startTime = Date.now();
        timerEl.textContent = '00:00';
        return setInterval(() => {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            timerEl.textContent = formatTime(elapsed);
        }, 1000);
    }

    // ==========================================================================
    // 5. Toast Notification System
    // ==========================================================================
    function showToast(message, type = 'info', duration = 5000) {
        const toastContainer = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        let iconName = 'info';
        if (type === 'success') iconName = 'check-circle-2';
        if (type === 'error') iconName = 'alert-triangle';

        toast.innerHTML = `
            <i data-lucide="${iconName}" class="toast-icon"></i>
            <span class="toast-message">${escapeHtml(message)}</span>
            <button class="toast-close" aria-label="Close">&times;</button>
        `;

        toastContainer.appendChild(toast);
        if (window.lucide) lucide.createIcons({ root: toast });

        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => removeToast(toast));

        if (duration > 0) {
            setTimeout(() => removeToast(toast), duration);
        }
    }

    function removeToast(toast) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px) scale(0.95)';
        setTimeout(() => toast.remove(), 250);
    }

    function escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    // ==========================================================================
    // 6. Research Report Generation & Polling
    // ==========================================================================
    researchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = researchQuery.value.trim();
        if (!query) {
            showToast('Please enter a research topic or query.', 'error');
            return;
        }

        // Reset UI state
        researchResult.classList.add('hidden');
        researchLoading.classList.remove('hidden');
        generateResearchBtn.disabled = true;
        generateResearchBtn.innerHTML = '<span class="spinner" style="width:16px;height:16px;display:inline-block;margin-right:8px;border-width:2px;"></span> Researching...';

        // Reset Steps
        resetResearchSteps();

        // Start Elapsed Timer
        clearInterval(researchTimerInterval);
        researchTimerInterval = startTimer(researchTimer);

        try {
            const resp = await fetch('/api/research', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });

            const data = await resp.json();

            if (!resp.ok || data.status === 'failed' || data.error) {
                throw new Error(data.error || 'Failed to start research task');
            }

            const taskId = data.task_id;
            showToast('Research task queued. Polling autonomous agent...', 'info');

            // Begin Polling
            pollResearchTask(taskId);

        } catch (err) {
            handleResearchError(err.message);
        }
    });

    function pollResearchTask(taskId) {
        clearInterval(researchPollInterval);
        researchPollInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/task/${taskId}`);
                if (!resp.ok) {
                    throw new Error(`Failed to check task: HTTP ${resp.status}`);
                }
                const data = await resp.json();

                // Dynamic progress hints
                updateResearchProgressHints(data);

                if (data.status === 'completed') {
                    clearInterval(researchPollInterval);
                    clearInterval(researchTimerInterval);
                    displayResearchResult(data);
                } else if (data.status === 'failed') {
                    clearInterval(researchPollInterval);
                    clearInterval(researchTimerInterval);
                    handleResearchError(data.error || 'Autonomous agent encountered an error');
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 2000);
    }

    function resetResearchSteps() {
        ['step-search', 'step-extract', 'step-compute', 'step-pdf'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.classList.remove('active', 'completed');
            }
        });
        document.getElementById('step-search')?.classList.add('active');
        researchProgressText.textContent = 'Searching arXiv and academic web sources...';
    }

    function updateResearchProgressHints(taskData) {
        if (taskData.progress_message) {
            researchProgressText.textContent = taskData.progress_message;
        }

        // Progress step animation based on progress message or elapsed time
        const elapsedText = researchTimer.textContent;
        const [mins, secs] = elapsedText.split(':').map(Number);
        const totalSecs = (mins || 0) * 60 + (secs || 0);

        if (totalSecs > 10) {
            document.getElementById('step-search')?.classList.add('completed');
            document.getElementById('step-extract')?.classList.add('active');
        }
        if (totalSecs > 30) {
            document.getElementById('step-extract')?.classList.add('completed');
            document.getElementById('step-compute')?.classList.add('active');
        }
        if (totalSecs > 60) {
            document.getElementById('step-compute')?.classList.add('completed');
            document.getElementById('step-pdf')?.classList.add('active');
        }
    }

    function displayResearchResult(taskData) {
        researchLoading.classList.add('hidden');
        generateResearchBtn.disabled = false;
        generateResearchBtn.innerHTML = '<i data-lucide="play" class="btn-icon"></i><span>Generate Research Report</span>';
        if (window.lucide) lucide.createIcons({ root: generateResearchBtn });

        // Fill Results
        const result = taskData.result || {};
        const topic = result.topic || taskData.query || 'Research Report';
        const summary = result.summary || 'Research report generated successfully.';
        const pdfFilename = result.pdf_path || 'report.pdf';

        researchResultTopic.textContent = topic;
        researchResultSummary.innerHTML = formatSummaryMarkdown(summary);

        // Sources list
        if (result.sources && Array.isArray(result.sources) && result.sources.length > 0) {
            researchSourcesList.innerHTML = '';
            result.sources.forEach(src => {
                const li = document.createElement('li');
                li.textContent = src;
                researchSourcesList.appendChild(li);
            });
            researchSourcesContainer.classList.remove('hidden');
        } else {
            researchSourcesContainer.classList.add('hidden');
        }

        // Download link
        researchDownloadBtn.href = `/api/download/${encodeURIComponent(pdfFilename)}`;
        researchDownloadBtn.setAttribute('download', pdfFilename);

        researchResult.classList.remove('hidden');
        if (window.lucide) lucide.createIcons({ root: researchResult });

        showToast('Research Report generated and compiled!', 'success');
    }

    function handleResearchError(errMsg) {
        researchLoading.classList.add('hidden');
        generateResearchBtn.disabled = false;
        generateResearchBtn.innerHTML = '<i data-lucide="play" class="btn-icon"></i><span>Generate Research Report</span>';
        if (window.lucide) lucide.createIcons({ root: generateResearchBtn });

        showToast(`Error: ${errMsg}`, 'error', 7000);
    }

    function formatSummaryMarkdown(text) {
        if (!text) return '';
        // Basic formatting for bold, italic, and paragraphs
        let html = escapeHtml(text);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        return html;
    }

    // ==========================================================================
    // 7. Math Paper Generation & Polling
    // ==========================================================================
    mathForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const topic = mathTopic.value.trim();
        const yearLevel = mathYearLevel.value.trim();
        const difficulty = mathDifficulty.value;
        const count = parseInt(mathCount.value, 10) || 5;
        const includeDiagrams = mathIncludeDiagrams ? mathIncludeDiagrams.checked : true;

        if (!topic) {
            showToast('Please specify a mathematical topic.', 'error');
            return;
        }

        // Reset UI state
        mathResult.classList.add('hidden');
        mathLoading.classList.remove('hidden');
        generateMathBtn.disabled = true;
        generateMathBtn.innerHTML = '<span class="spinner" style="width:16px;height:16px;display:inline-block;margin-right:8px;border-width:2px;"></span> Generating...';

        // Reset Math Steps
        resetMathSteps();

        // Start Timer
        clearInterval(mathTimerInterval);
        mathTimerInterval = startTimer(mathTimer);

        try {
            const resp = await fetch('/api/math', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic,
                    year_level: yearLevel,
                    difficulty,
                    count,
                    include_diagrams: includeDiagrams
                })
            });

            const data = await resp.json();

            if (!resp.ok || data.status === 'failed' || data.error) {
                throw new Error(data.error || 'Failed to start math paper generation');
            }

            const taskId = data.task_id;
            showToast('Math problem generation initiated...', 'info');

            pollMathTask(taskId);

        } catch (err) {
            handleMathError(err.message);
        }
    });

    function pollMathTask(taskId) {
        clearInterval(mathPollInterval);
        mathPollInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/task/${taskId}`);
                if (!resp.ok) {
                    throw new Error(`Failed to check math task: HTTP ${resp.status}`);
                }
                const data = await resp.json();

                updateMathProgressHints(data);

                if (data.status === 'completed') {
                    clearInterval(mathPollInterval);
                    clearInterval(mathTimerInterval);
                    displayMathResult(data);
                } else if (data.status === 'failed') {
                    clearInterval(mathPollInterval);
                    clearInterval(mathTimerInterval);
                    handleMathError(data.error || 'Math generation failed');
                }
            } catch (err) {
                console.error('Math polling error:', err);
            }
        }, 2000);
    }

    function resetMathSteps() {
        ['math-step-generate', 'math-step-tex', 'math-step-compile'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.classList.remove('active', 'completed');
            }
        });
        document.getElementById('math-step-generate')?.classList.add('active');
        mathProgressText.textContent = 'Contacting LLM to design math problems...';
    }

    function updateMathProgressHints(taskData) {
        if (taskData.progress_message) {
            mathProgressText.textContent = taskData.progress_message;
        }

        const elapsedText = mathTimer.textContent;
        const [mins, secs] = elapsedText.split(':').map(Number);
        const totalSecs = (mins || 0) * 60 + (secs || 0);

        if (totalSecs > 5) {
            document.getElementById('math-step-generate')?.classList.add('completed');
            document.getElementById('math-step-tex')?.classList.add('active');
        }
        if (totalSecs > 10) {
            document.getElementById('math-step-tex')?.classList.add('completed');
            document.getElementById('math-step-compile')?.classList.add('active');
        }
    }

    function displayMathResult(taskData) {
        mathLoading.classList.add('hidden');
        generateMathBtn.disabled = false;
        generateMathBtn.innerHTML = '<i data-lucide="file-text" class="btn-icon"></i><span>Generate Math Paper & Solutions</span>';
        if (window.lucide) lucide.createIcons({ root: generateMathBtn });

        const result = taskData.result || {};
        const title = result.title || `${taskData.year_level || ''} Math: ${taskData.topic || 'Practice Paper'}`;
        const count = taskData.count || 5;
        const difficulty = taskData.difficulty || 'Medium';
        const yearLevel = taskData.year_level || 'Year 10';

        mathResultTitle.textContent = title;
        mathResultSubtitle.textContent = `${count} problems • ${yearLevel} • ${difficulty} Difficulty`;

        // Downloads
        const worksheetPath = result.worksheet_path || 'math_worksheet.pdf';
        const answersPath = result.answers_path || 'math_worksheet_answers.pdf';

        mathWorksheetDownloadBtn.href = `/api/download/${encodeURIComponent(worksheetPath)}`;
        mathWorksheetDownloadBtn.setAttribute('download', worksheetPath);

        mathAnswersDownloadBtn.href = `/api/download/${encodeURIComponent(answersPath)}`;
        mathAnswersDownloadBtn.setAttribute('download', answersPath);

        mathResult.classList.remove('hidden');
        if (window.lucide) lucide.createIcons({ root: mathResult });

        showToast('Worksheet and Answer Key PDFs compiled successfully!', 'success');
    }

    function handleMathError(errMsg) {
        mathLoading.classList.add('hidden');
        generateMathBtn.disabled = false;
        generateMathBtn.innerHTML = '<i data-lucide="file-text" class="btn-icon"></i><span>Generate Math Paper & Solutions</span>';
        if (window.lucide) lucide.createIcons({ root: generateMathBtn });

        showToast(`Error: ${errMsg}`, 'error', 7000);
    }
});
