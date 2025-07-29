<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GoldTrackBot - Real-Time Gold Price Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .price-up {
            animation: pulseGreen 2s infinite;
        }
        .price-down {
            animation: pulseRed 2s infinite;
        }
        @keyframes pulseGreen {
            0% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(74, 222, 128, 0); }
            100% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
        }
        @keyframes pulseRed {
            0% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(248, 113, 113, 0); }
            100% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0); }
        }
        .sentiment-positive {
            background: linear-gradient(90deg, rgba(74,222,128,0.1) 0%, rgba(74,222,128,0.3) 100%);
        }
        .sentiment-negative {
            background: linear-gradient(90deg, rgba(248,113,113,0.1) 0%, rgba(248,113,113,0.3) 100%);
        }
        .sentiment-neutral {
            background: linear-gradient(90deg, rgba(156,163,175,0.1) 0%, rgba(156,163,175,0.3) 100%);
        }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <header class="flex flex-col md:flex-row justify-between items-center mb-8">
            <div class="flex items-center mb-4 md:mb-0">
                <i class="fas fa-coins text-yellow-500 text-4xl mr-3"></i>
                <div>
                    <h1 class="text-3xl font-bold text-gray-800">GoldTrackBot</h1>
                    <p class="text-gray-600">Real-Time Gold Price Monitor & Alert System</p>
                </div>
            </div>
            <div class="flex flex-col space-y-2">
                <div class="flex items-center space-x-2">
                    <div class="relative">
                        <input type="password" id="fmpApiKeyInput" placeholder="FMP API Key" class="pl-4 pr-10 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent">
                        <button id="saveFmpApiKey" class="absolute right-2 top-2 text-gray-500 hover:text-yellow-600">
                            <i class="fas fa-save"></i>
                        </button>
                    </div>
                    <a href="https://financialmodelingprep.com/developer/docs/" target="_blank" class="text-yellow-600 hover:text-yellow-700 text-sm" title="Get API Key">
                        <i class="fas fa-key"></i>
                    </a>
                </div>
                <div class="flex items-center space-x-2">
                    <div class="relative">
                        <input type="password" id="telegramBotTokenInput" placeholder="Telegram Bot Token" class="pl-4 pr-10 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent">
                        <button id="saveTelegramToken" class="absolute right-2 top-2 text-gray-500 hover:text-yellow-600">
                            <i class="fas fa-save"></i>
                        </button>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <div class="relative">
                        <input type="text" id="telegramChatIdInput" placeholder="Telegram Chat ID" class="pl-4 pr-10 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent">
                        <button id="saveTelegramChatId" class="absolute right-2 top-2 text-gray-500 hover:text-yellow-600">
                            <i class="fas fa-save"></i>
                        </button>
                    </div>
                </div>
                <div id="apiKeysStatus" class="text-xs text-gray-500">
                    <i class="fas fa-circle text-gray-400 mr-1"></i> API Keys not configured
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <div class="relative">
                    <input type="text" placeholder="Search..." class="pl-10 pr-4 py-2 rounded-full border border-gray-300 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent">
                    <i class="fas fa-search absolute left-3 top-3 text-gray-400"></i>
                </div>
                <button class="bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded-full transition duration-300">
                    <i class="fas fa-bell mr-2"></i>Alerts
                </button>
            </div>
        </header>

        <!-- Main Dashboard -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <!-- Current Price Card -->
            <div class="bg-white rounded-xl shadow-md p-6 flex flex-col items-center justify-center price-up" id="priceCard">
                <div class="flex items-center mb-4">
                    <i class="fas fa-chart-line text-yellow-500 text-2xl mr-2"></i>
                    <h2 class="text-xl font-semibold text-gray-700">Current Gold Price</h2>
                </div>
                <div class="text-4xl font-bold text-gray-800 mb-2" id="currentPrice">$1,832.45</div>
                <div class="flex items-center text-green-500 mb-4" id="priceChange">
                    <i class="fas fa-caret-up mr-1"></i>
                    <span>+12.34 (0.68%)</span>
                </div>
                <div class="text-gray-500 text-sm">Last updated: <span id="lastUpdated">Just now</span></div>
            </div>

            <!-- Prediction Card -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <div class="flex items-center mb-4">
                    <i class="fas fa-robot text-blue-500 text-2xl mr-2"></i>
                    <h2 class="text-xl font-semibold text-gray-700">AI Prediction</h2>
                </div>
                <div class="mb-4">
                    <div class="flex justify-between text-sm text-gray-600 mb-1">
                        <span>Next 6 hours:</span>
                        <span id="predictionConfidence">82% confidence</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2.5">
                        <div class="bg-blue-500 h-2.5 rounded-full" style="width: 82%"></div>
                    </div>
                </div>
                <div class="flex items-center justify-center mb-4">
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600 mb-1" id="predictionDirection">Upward</div>
                        <div class="text-gray-500 text-sm">Trend prediction</div>
                    </div>
                </div>
                <div class="text-sm text-gray-600">
                    <i class="fas fa-info-circle mr-1 text-blue-400"></i>
                    <span id="predictionText">Model expects continued growth based on recent patterns</span>
                </div>
            </div>

            <!-- Telegram Bot Card -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <div class="flex items-center mb-4">
                    <i class="fab fa-telegram text-blue-400 text-2xl mr-2"></i>
                    <h2 class="text-xl font-semibold text-gray-700">Telegram Bot</h2>
                </div>
                <div class="mb-4">
                    <div class="flex items-center bg-blue-50 rounded-lg p-3 mb-2">
                        <i class="fas fa-check-circle text-green-500 mr-3"></i>
                        <div>
                            <div class="font-medium">Connected</div>
                            <div class="text-xs text-gray-500">Last message received: 2 min ago</div>
                        </div>
                    </div>
                    <div class="space-y-2">
                        <div class="flex items-center">
                            <i class="fas fa-terminal text-gray-400 mr-3 w-5 text-center"></i>
                            <span class="text-sm font-mono">/fiyat</span>
                        </div>
                        <div class="flex items-center">
                            <i class="fas fa-terminal text-gray-400 mr-3 w-5 text-center"></i>
                            <span class="text-sm font-mono">/durum</span>
                        </div>
                        <div class="flex items-center">
                            <i class="fas fa-bell text-gray-400 mr-3 w-5 text-center"></i>
                            <span class="text-sm">Alerts enabled</span>
                        </div>
                    </div>
                </div>
                <button class="w-full bg-blue-400 hover:bg-blue-500 text-white py-2 rounded-lg transition duration-300 flex items-center justify-center">
                    <i class="fab fa-telegram mr-2"></i> Open Telegram
                </button>
            </div>
        </div>

        <!-- News and Alerts Section -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- News Sentiment -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center">
                        <i class="fas fa-newspaper text-purple-500 text-2xl mr-2"></i>
                        <h2 class="text-xl font-semibold text-gray-700">Market News</h2>
                    </div>
                    <span class="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-xs font-medium">Sentiment Analysis</span>
                </div>
                
                <div class="space-y-4" id="newsContainer">
                    <!-- News items will be added here by JavaScript -->
                </div>
            </div>

            <!-- Alerts History -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center">
                        <i class="fas fa-bell text-red-500 text-2xl mr-2"></i>
                        <h2 class="text-xl font-semibold text-gray-700">Recent Alerts</h2>
                    </div>
                    <span class="px-3 py-1 bg-red-100 text-red-800 rounded-full text-xs font-medium">Opportunity Detection</span>
                </div>
                
                <div class="space-y-4" id="alertsContainer">
                    <!-- Alert items will be added here by JavaScript -->
                </div>
            </div>
        </div>

        <!-- Historical Data Section -->
        <div class="mt-8 bg-white rounded-xl shadow-md p-6">
            <div class="flex items-center justify-between mb-6">
                <div class="flex items-center">
                    <i class="fas fa-chart-bar text-green-500 text-2xl mr-2"></i>
                    <h2 class="text-xl font-semibold text-gray-700">Historical Price Data</h2>
                </div>
                <div class="flex space-x-2">
                    <button class="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-sm">24h</button>
                    <button class="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-sm">7d</button>
                    <button class="px-3 py-1 bg-yellow-500 text-white rounded-lg text-sm">30d</button>
                    <button class="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-sm">1y</button>
                </div>
            </div>
            
            <div class="h-64">
                <canvas id="priceChart"></canvas>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // API Keys Management
        const API_KEYS = {
            FMP_API_KEY: 'goldtrackbot_fmp_api_key',
            TELEGRAM_TOKEN: 'goldtrackbot_telegram_token',
            TELEGRAM_CHAT_ID: 'goldtrackbot_telegram_chat_id'
        };
        
        // Check for saved API keys on load
        document.addEventListener('DOMContentLoaded', function() {
            const statusElement = document.getElementById('apiKeysStatus');
            let allKeysConfigured = true;
            
            // Check and populate FMP API Key
            const fmpApiKey = localStorage.getItem(API_KEYS.FMP_API_KEY);
            if (fmpApiKey) {
                document.getElementById('fmpApiKeyInput').value = '••••••••••••••••';
            } else {
                allKeysConfigured = false;
            }
            
            // Check and populate Telegram Bot Token
            const telegramToken = localStorage.getItem(API_KEYS.TELEGRAM_TOKEN);
            if (telegramToken) {
                document.getElementById('telegramBotTokenInput').value = '••••••••••••••••';
            } else {
                allKeysConfigured = false;
            }
            
            // Check and populate Telegram Chat ID
            const telegramChatId = localStorage.getItem(API_KEYS.TELEGRAM_CHAT_ID);
            if (telegramChatId) {
                document.getElementById('telegramChatIdInput').value = '••••••••••••••••';
            } else {
                allKeysConfigured = false;
            }
            
            // Update status
            if (allKeysConfigured) {
                statusElement.className = 'text-xs text-green-600';
                statusElement.innerHTML = '<i class="fas fa-check-circle mr-1"></i> All API keys configured';
                fetchGoldPrice();
            } else {
                statusElement.className = 'text-xs text-red-600';
                statusElement.innerHTML = '<i class="fas fa-exclamation-circle mr-1"></i> Some API keys missing';
            }

            // Save FMP API Key handler
            document.getElementById('saveFmpApiKey').addEventListener('click', function() {
                const apiKey = document.getElementById('fmpApiKeyInput').value.trim();
                if (apiKey && apiKey.length > 20) {
                    localStorage.setItem(API_KEYS.FMP_API_KEY, apiKey);
                    document.getElementById('fmpApiKeyInput').value = '••••••••••••••••';
                    updateKeysStatus();
                    fetchGoldPrice();
                } else {
                    showKeyError('Invalid FMP API Key');
                }
            });

            // Save Telegram Bot Token handler
            document.getElementById('saveTelegramToken').addEventListener('click', function() {
                const token = document.getElementById('telegramBotTokenInput').value.trim();
                if (token && token.length > 20) {
                    localStorage.setItem(API_KEYS.TELEGRAM_TOKEN, token);
                    document.getElementById('telegramBotTokenInput').value = '••••••••••••••••';
                    updateKeysStatus();
                } else {
                    showKeyError('Invalid Telegram Token');
                }
            });

            // Save Telegram Chat ID handler
            document.getElementById('saveTelegramChatId').addEventListener('click', function() {
                const chatId = document.getElementById('telegramChatIdInput').value.trim();
                if (chatId && !isNaN(chatId)) {
                    localStorage.setItem(API_KEYS.TELEGRAM_CHAT_ID, chatId);
                    document.getElementById('telegramChatIdInput').value = '••••••••••••••••';
                    updateKeysStatus();
                } else {
                    showKeyError('Invalid Chat ID');
                }
            });
        });

        function updateKeysStatus() {
            const statusElement = document.getElementById('apiKeysStatus');
            const hasFmpKey = !!localStorage.getItem(API_KEYS.FMP_API_KEY);
            const hasTelegramToken = !!localStorage.getItem(API_KEYS.TELEGRAM_TOKEN);
            const hasChatId = !!localStorage.getItem(API_KEYS.TELEGRAM_CHAT_ID);
            
            if (hasFmpKey && hasTelegramToken && hasChatId) {
                statusElement.className = 'text-xs text-green-600';
                statusElement.innerHTML = '<i class="fas fa-check-circle mr-1"></i> All API keys configured';
            } else {
                statusElement.className = 'text-xs text-yellow-600';
                const missingKeys = [];
                if (!hasFmpKey) missingKeys.push('FMP');
                if (!hasTelegramToken) missingKeys.push('Telegram Token');
                if (!hasChatId) missingKeys.push('Chat ID');
                statusElement.innerHTML = `<i class="fas fa-exclamation-triangle mr-1"></i> Missing: ${missingKeys.join(', ')}`;
            }
        }

        function showKeyError(message) {
            const statusElement = document.getElementById('apiKeysStatus');
            statusElement.className = 'text-xs text-red-600';
            statusElement.innerHTML = `<i class="fas fa-exclamation-circle mr-1"></i> ${message}`;
            setTimeout(updateKeysStatus, 3000);
        }

        // Real API Fetch Functions
        async function fetchGoldPrice() {
            const apiKey = localStorage.getItem(API_KEYS.FMP_API_KEY);
            if (!apiKey) {
                console.warn('No FMP API key set - using sample data');
                document.getElementById('apiKeysStatus').className = 'text-xs text-red-600';
                document.getElementById('apiKeysStatus').innerHTML = '<i class="fas fa-exclamation-circle mr-1"></i> FMP API Key required for real data';
                return false;
            }

            try {
                const response = await fetch(`https://financialmodelingprep.com/api/v3/gold?apikey=${apiKey}`);
                if (!response.ok) throw new Error('API request failed');
                
                const data = await response.json();
                if (!data || data.length === 0) throw new Error('No gold price data returned');
                
                // Update UI with real data
                const price = data[0].price;
                document.getElementById('currentPrice').textContent = `${price.toFixed(2)}`;
                document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
                
                return true;
            } catch (error) {
                console.error('Error fetching gold price:', error);
                document.getElementById('apiKeyStatus').className = 'text-xs text-red-600';
                document.getElementById('apiKeyStatus').innerHTML = `<i class="fas fa-exclamation-circle mr-1"></i> ${error.message}`;
                return false;
            }
        }

        // Initialize with real data if possible
        const sampleNews = [
            {
                title: "Fed Signals Potential Rate Cuts in Coming Months",
                source: "Financial Times",
                time: "2 hours ago",
                sentiment: "positive"
            },
            {
                title: "Geopolitical Tensions Rise in Middle East",
                source: "Reuters",
                time: "5 hours ago",
                sentiment: "positive"
            },
            {
                title: "Strong Dollar Puts Pressure on Gold Prices",
                source: "Bloomberg",
                time: "8 hours ago",
                sentiment: "negative"
            },
            {
                title: "Gold Mining Production Hits 3-Month High",
                source: "Mining Weekly",
                time: "1 day ago",
                sentiment: "neutral"
            }
        ];

        const sampleAlerts = [
            {
                type: "price_drop",
                message: "Price dropped 1.2% in last hour - potential buying opportunity",
                time: "45 minutes ago",
                severity: "medium"
            },
            {
                type: "sentiment_shift",
                message: "Positive news sentiment detected with 85% confidence",
                time: "3 hours ago",
                severity: "low"
            },
            {
                type: "prediction_alert",
                message: "AI predicts 78% chance of price increase in next 6 hours",
                time: "6 hours ago",
                severity: "high"
            }
        ];

        // Initialize the UI with sample data
        document.addEventListener('DOMContentLoaded', function() {
            // Populate news
            const newsContainer = document.getElementById('newsContainer');
            sampleNews.forEach(news => {
                const sentimentClass = `sentiment-${news.sentiment}`;
                const sentimentIcon = news.sentiment === 'positive' ? 'fa-face-smile' : 
                                     news.sentiment === 'negative' ? 'fa-face-frown' : 'fa-face-meh';
                const sentimentColor = news.sentiment === 'positive' ? 'text-green-500' : 
                                     news.sentiment === 'negative' ? 'text-red-500' : 'text-gray-500';
                
                const newsItem = document.createElement('div');
                newsItem.className = `p-4 rounded-lg ${sentimentClass}`;
                newsItem.innerHTML = `
                    <div class="flex justify-between items-start mb-1">
                        <h3 class="font-medium text-gray-800">${news.title}</h3>
                        <i class="fas ${sentimentIcon} ${sentimentColor}"></i>
                    </div>
                    <div class="flex justify-between text-sm text-gray-500">
                        <span>${news.source}</span>
                        <span>${news.time}</span>
                    </div>
                `;
                newsContainer.appendChild(newsItem);
            });

            // Populate alerts
            const alertsContainer = document.getElementById('alertsContainer');
            sampleAlerts.forEach(alert => {
                const severityColor = alert.severity === 'high' ? 'bg-red-100 text-red-800' : 
                                    alert.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' : 'bg-blue-100 text-blue-800';
                
                const alertItem = document.createElement('div');
                alertItem.className = 'p-4 border border-gray-200 rounded-lg';
                alertItem.innerHTML = `
                    <div class="flex items-start">
                        <div class="flex-shrink-0 mt-1">
                            <span class="px-2 py-1 ${severityColor} rounded-full text-xs font-medium">${alert.type.replace('_', ' ')}</span>
                        </div>
                        <div class="ml-3">
                            <p class="text-sm text-gray-800">${alert.message}</p>
                            <p class="text-xs text-gray-500 mt-1">${alert.time}</p>
                        </div>
                    </div>
                `;
                alertsContainer.appendChild(alertItem);
            });

            // Initialize chart
            const ctx = document.getElementById('priceChart').getContext('2d');
            const priceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array.from({length: 30}, (_, i) => `${i+1} Oct`),
                    datasets: [{
                        label: 'Gold Price (USD/oz)',
                        data: Array.from({length: 30}, () => Math.floor(1800 + Math.random() * 100)),
                        borderColor: 'rgb(234, 179, 8)',
                        backgroundColor: 'rgba(234, 179, 8, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false
                        }
                    }
                }
            });

            // Price updates
            let currentPrice = 1832.45;
            setInterval(async () => {
                // Try to get real data first
                const realDataSuccess = await fetchGoldPrice();
                
                if (!realDataSuccess) {
                    // Fallback to simulated data if API fails
                    const change = (Math.random() - 0.5) * 5;
                    currentPrice += change;
                    currentPrice = Math.round(currentPrice * 100) / 100;
                } else {
                    // If real data was fetched, currentPrice was updated by fetchGoldPrice()
                    return; // Skip the simulated update below
                }
                
                const changeElement = document.getElementById('priceChange');
                const priceCard = document.getElementById('priceCard');
                
                // Update price display
                document.getElementById('currentPrice').textContent = `$${currentPrice.toFixed(2)}`;
                
                // Update change indicator
                if (change > 0) {
                    changeElement.className = "flex items-center text-green-500 mb-4";
                    changeElement.innerHTML = `<i class="fas fa-caret-up mr-1"></i><span>+${Math.abs(change).toFixed(2)} (${(Math.abs(change)/currentPrice*100).toFixed(2)}%)</span>`;
                    priceCard.classList.remove('price-down');
                    priceCard.classList.add('price-up');
                } else {
                    changeElement.className = "flex items-center text-red-500 mb-4";
                    changeElement.innerHTML = `<i class="fas fa-caret-down mr-1"></i><span>-${Math.abs(change).toFixed(2)} (${(Math.abs(change)/currentPrice*100).toFixed(2)}%)</span>`;
                    priceCard.classList.remove('price-up');
                    priceCard.classList.add('price-down');
                }
                
                // Update timestamp
                document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
                
                // Randomly update prediction (simulating model updates)
                if (Math.random() > 0.7) {
                    const confidence = Math.floor(Math.random() * 50) + 50;
                    const direction = Math.random() > 0.5 ? 'Upward' : 'Downward';
                    const reasons = [
                        "based on recent patterns",
                        "due to market volatility",
                        "considering economic indicators",
                        "aligned with seasonal trends"
                    ];
                    
                    document.getElementById('predictionConfidence').textContent = `${confidence}% confidence`;
                    document.getElementById('predictionDirection').textContent = direction;
                    document.getElementById('predictionDirection').className = `text-2xl font-bold mb-1 ${direction === 'Upward' ? 'text-blue-600' : 'text-red-600'}`;
                    document.getElementById('predictionText').textContent = `Model expects ${direction.toLowerCase()} movement ${reasons[Math.floor(Math.random() * reasons.length)]}`;
                    
                    // Update confidence bar
                    document.querySelector('#predictionConfidence').nextElementSibling.firstElementChild.style.width = `${confidence}%`;
                    document.querySelector('#predictionConfidence').nextElementSibling.firstElementChild.className = `h-2.5 rounded-full ${direction === 'Upward' ? 'bg-blue-500' : 'bg-red-500'}`;
                }
            }, 5000);
        });
    </script>
</body>
</html>
