<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gold Tracker & Telegram Bot</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        gold: '#FFD700',
                        'gold-dark': '#D4AF37',
                    }
                }
            }
        }
    </script>
    <style>
        .price-up {
            animation: pulseGreen 2s infinite;
        }
        .price-down {
            animation: pulseRed 2s infinite;
        }
        @keyframes pulseGreen {
            0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
            100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }
        @keyframes pulseRed {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .chart-container {
            height: 300px;
        }
        .sentiment-positive {
            background: linear-gradient(90deg, rgba(34,197,94,0.1) 0%, rgba(34,197,94,0.3) 100%);
        }
        .sentiment-negative {
            background: linear-gradient(90deg, rgba(239,68,68,0.1) 0%, rgba(239,68,68,0.3) 100%);
        }
        .sentiment-neutral {
            background: linear-gradient(90deg, rgba(156,163,175,0.1) 0%, rgba(156,163,175,0.3) 100%);
        }
    </style>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen">
        <!-- Header -->
        <header class="bg-gradient-to-r from-gold-dark to-gold text-white shadow-lg">
            <div class="container mx-auto px-4 py-6">
                <div class="flex flex-col md:flex-row justify-between items-center">
                    <div class="flex items-center mb-4 md:mb-0">
                        <i class="fas fa-coins text-3xl mr-3"></i>
                        <div>
                            <h1 class="text-2xl font-bold">Gold Tracker</h1>
                            <p class="text-sm opacity-80">Real-time gold prices with Telegram notifications</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-4">
                        <div class="bg-white bg-opacity-20 px-4 py-2 rounded-full">
                            <span class="text-sm">Live</span>
                            <span class="ml-2 w-3 h-3 inline-block rounded-full bg-red-500 animate-pulse"></span>
                        </div>
                        <button class="bg-white text-gold-dark px-4 py-2 rounded-lg font-medium hover:bg-opacity-90 transition">
                            <i class="fab fa-telegram mr-2"></i> Connect Telegram
                        </button>
                    </div>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="container mx-auto px-4 py-8">
            <!-- Current Price Section -->
            <section class="mb-12">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- Current Price Card -->
                    <div class="bg-white rounded-xl shadow-md p-6 flex flex-col items-center price-up">
                        <div class="flex items-center mb-4">
                            <i class="fas fa-chart-line text-2xl text-green-500 mr-3"></i>
                            <h2 class="text-xl font-semibold">Current Gold Price</h2>
                        </div>
                        <div class="text-center">
                            <p class="text-4xl font-bold text-gold-dark my-3">$1,924.56</p>
                            <div class="flex justify-center items-center">
                                <span class="text-green-500 font-medium mr-2">
                                    <i class="fas fa-caret-up mr-1"></i> 1.24%
                                </span>
                                <span class="text-gray-500 text-sm">+$23.50 today</span>
                            </div>
                        </div>
                    </div>

                    <!-- Prediction Card -->
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <div class="flex items-center mb-4">
                            <i class="fas fa-brain text-2xl text-purple-500 mr-3"></i>
                            <h2 class="text-xl font-semibold">ML Prediction</h2>
                        </div>
                        <div class="flex flex-col items-center">
                            <div class="w-full bg-gray-200 rounded-full h-4 mb-3">
                                <div class="bg-green-500 h-4 rounded-full" style="width: 72%"></div>
                            </div>
                            <p class="text-lg font-medium text-green-600 mb-1">72% Confidence</p>
                            <p class="text-gray-600">Next 6 hours: <span class="font-medium">Upward Trend</span></p>
                        </div>
                    </div>

                    <!-- Telegram Status Card -->
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <div class="flex items-center mb-4">
                            <i class="fab fa-telegram text-2xl text-blue-400 mr-3"></i>
                            <h2 class="text-xl font-semibold">Telegram Bot</h2>
                        </div>
                        <div class="space-y-3">
                            <div class="flex items-center">
                                <div class="w-3 h-3 rounded-full bg-green-500 mr-2"></div>
                                <span>Status: <span class="font-medium">Connected</span></span>
                            </div>
                            <div class="flex items-center">
                                <i class="fas fa-bell text-yellow-500 mr-2"></i>
                                <span>Active Alerts: <span class="font-medium">3</span></span>
                            </div>
                            <div class="flex items-center">
                                <i class="fas fa-user-friends text-blue-500 mr-2"></i>
                                <span>Subscribers: <span class="font-medium">142</span></span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Charts and Data Section -->
            <section class="mb-12">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <!-- Price Chart -->
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <div class="flex justify-between items-center mb-6">
                            <h2 class="text-xl font-semibold">Gold Price (24h)</h2>
                            <div class="flex space-x-2">
                                <button class="px-3 py-1 bg-gray-100 rounded text-sm">1D</button>
                                <button class="px-3 py-1 bg-gray-100 rounded text-sm">1W</button>
                                <button class="px-3 py-1 bg-gold-dark text-white rounded text-sm">1M</button>
                                <button class="px-3 py-1 bg-gray-100 rounded text-sm">1Y</button>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas id="priceChart"></canvas>
                        </div>
                    </div>

                    <!-- Sentiment Analysis -->
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <h2 class="text-xl font-semibold mb-6">Market Sentiment</h2>
                        <div class="space-y-4">
                            <div class="sentiment-positive p-4 rounded-lg">
                                <div class="flex justify-between items-center">
                                    <div>
                                        <h3 class="font-medium">Fed signals potential rate cuts</h3>
                                        <p class="text-sm text-gray-600">Bloomberg - 2 hours ago</p>
                                    </div>
                                    <span class="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">Positive</span>
                                </div>
                            </div>
                            <div class="sentiment-negative p-4 rounded-lg">
                                <div class="flex justify-between items-center">
                                    <div>
                                        <h3 class="font-medium">Dollar strengthens against major currencies</h3>
                                        <p class="text-sm text-gray-600">Reuters - 4 hours ago</p>
                                    </div>
                                    <span class="px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs">Negative</span>
                                </div>
                            </div>
                            <div class="sentiment-neutral p-4 rounded-lg">
                                <div class="flex justify-between items-center">
                                    <div>
                                        <h3 class="font-medium">Gold reserves remain stable in Q2</h3>
                                        <p class="text-sm text-gray-600">Financial Times - 6 hours ago</p>
                                    </div>
                                    <span class="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs">Neutral</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Alerts and Settings Section -->
            <section>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <!-- Recent Alerts -->
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <h2 class="text-xl font-semibold mb-6">Recent Alerts</h2>
                        <div class="space-y-4">
                            <div class="border-l-4 border-green-500 pl-4 py-2">
                                <div class="flex justify-between">
                                    <h3 class="font-medium">Buy Opportunity</h3>
                                    <span class="text-sm text-gray-500">10 min ago</span>
                                </div>
                                <p class="text-sm text-gray-600">Gold price dropped 1.2% in last hour. Good entry point according to ML model.</p>
                            </div>
                            <div class="border-l-4 border-red-500 pl-4 py-2">
                                <div class="flex justify-between">
                                    <h3 class="font-medium">Price Drop Warning</h3>
                                    <span class="text-sm text-gray-500">2 hours ago</span>
                                </div>
                                <p class="text-sm text-gray-600">Negative market sentiment detected. Possible downward trend.</p>
                            </div>
                            <div class="border-l-4 border-blue-500 pl-4 py-2">
                                <div class="flex justify-between">
                                    <h3 class="font-medium">News Alert</h3>
                                    <span class="text-sm text-gray-500">4 hours ago</span>
                                </div>
                                <p class="text-sm text-gray-600">Fed announcement coming soon. High volatility expected.</p>
                            </div>
                        </div>
                    </div>

                    <!-- Notification Settings -->
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <h2 class="text-xl font-semibold mb-6">Notification Settings</h2>
                        <form>
                            <div class="space-y-4">
                                <div>
                                    <label class="flex items-center">
                                        <input type="checkbox" class="form-checkbox text-gold-dark" checked>
                                        <span class="ml-2">Price change alerts</span>
                                    </label>
                                    <div class="ml-6 mt-2">
                                        <select class="border rounded px-3 py-1 text-sm">
                                            <option>Notify when price changes by 0.5%</option>
                                            <option selected>Notify when price changes by 1%</option>
                                            <option>Notify when price changes by 2%</option>
                                        </select>
                                    </div>
                                </div>
                                <div>
                                    <label class="flex items-center">
                                        <input type="checkbox" class="form-checkbox text-gold-dark" checked>
                                        <span class="ml-2">ML prediction alerts</span>
                                    </label>
                                </div>
                                <div>
                                    <label class="flex items-center">
                                        <input type="checkbox" class="form-checkbox text-gold-dark">
                                        <span class="ml-2">News sentiment alerts</span>
                                    </label>
                                </div>
                                <div>
                                    <label class="flex items-center">
                                        <input type="checkbox" class="form-checkbox text-gold-dark" checked>
                                        <span class="ml-2">Daily summary</span>
                                    </label>
                                </div>
                            </div>
                            <button type="submit" class="mt-6 bg-gold-dark text-white px-4 py-2 rounded-lg hover:bg-opacity-90 transition">
                                Save Settings
                            </button>
                        </form>
                    </div>
                </div>
            </section>
        </main>

        <!-- Footer -->
        <footer class="bg-gray-800 text-white py-8">
            <div class="container mx-auto px-4">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <div>
                        <h3 class="text-lg font-semibold mb-4">Gold Tracker</h3>
                        <p class="text-gray-400">Real-time gold price tracking with machine learning predictions and Telegram notifications.</p>
                    </div>
                    <div>
                        <h3 class="text-lg font-semibold mb-4">Quick Links</h3>
                        <ul class="space-y-2">
                            <li><a href="#" class="text-gray-400 hover:text-white transition">Documentation</a></li>
                            <li><a href="#" class="text-gray-400 hover:text-white transition">API Reference</a></li>
                            <li><a href="#" class="text-gray-400 hover:text-white transition">Telegram Bot</a></li>
                        </ul>
                    </div>
                    <div>
                        <h3 class="text-lg font-semibold mb-4">Connect</h3>
                        <div class="flex space-x-4">
                            <a href="#" class="text-gray-400 hover:text-white transition"><i class="fab fa-telegram text-xl"></i></a>
                            <a href="#" class="text-gray-400 hover:text-white transition"><i class="fab fa-twitter text-xl"></i></a>
                            <a href="#" class="text-gray-400 hover:text-white transition"><i class="fab fa-github text-xl"></i></a>
                        </div>
                    </div>
                </div>
                <div class="border-t border-gray-700 mt-8 pt-6 text-center text-gray-400">
                    <p>© 2023 Gold Tracker. All rights reserved.</p>
                </div>
            </div>
        </footer>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // Price Chart
        const priceCtx = document.getElementById('priceChart').getContext('2d');
        const priceChart = new Chart(priceCtx, {
            type: 'line',
            data: {
                labels: Array.from({length: 24}, (_, i) => `${i}:00`),
                datasets: [{
                    label: 'Gold Price (USD)',
                    data: [1910, 1912, 1915, 1918, 1920, 1922, 1921, 1920, 1918, 1916, 1915, 1917, 
                           1918, 1919, 1920, 1921, 1922, 1923, 1924, 1925, 1924, 1923, 1924, 1925],
                    borderColor: '#FFD700',
                    backgroundColor: 'rgba(255, 215, 0, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });

        // Simulate price updates
        function updatePrice() {
            const currentPriceEl = document.querySelector('.price-up');
            const priceEl = document.querySelector('.text-4xl');
            const changeEl = document.querySelector('.text-green-500');
            
            // Random price change
            const currentPrice = parseFloat(priceEl.textContent.replace('$', '').replace(',', ''));
            const change = (Math.random() - 0.5) * 5;
            const newPrice = currentPrice + change;
            const percentChange = (change / currentPrice * 100).toFixed(2);
            
            // Update UI
            priceEl.textContent = `$${newPrice.toFixed(2)}`;
            
            if (change > 0) {
                changeEl.innerHTML = `<i class="fas fa-caret-up mr-1"></i> ${percentChange}%`;
                changeEl.className = 'text-green-500 font-medium mr-2';
                currentPriceEl.classList.remove('price-down');
                currentPriceEl.classList.add('price-up');
            } else {
                changeEl.innerHTML = `<i class="fas fa-caret-down mr-1"></i> ${Math.abs(percentChange)}%`;
                changeEl.className = 'text-red-500 font-medium mr-2';
                currentPriceEl.classList.remove('price-up');
                currentPriceEl.classList.add('price-down');
            }
            
            // Update chart
            const newData = priceChart.data.datasets[0].data.slice(1);
            newData.push(newPrice);
            priceChart.data.datasets[0].data = newData;
            priceChart.update();
        }

        // Update price every 5 seconds
        setInterval(updatePrice, 5000);

        // Telegram bot simulation
        document.querySelector('.bg-white button').addEventListener('click', function() {
            alert('Telegram bot connected successfully! You will now receive notifications.');
        });
    </script>
</body>
</html>
