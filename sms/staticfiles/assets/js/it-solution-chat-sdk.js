// IT Solution Bot SDK
(function() {
    window.ITSolutionChatSDK = {
        config: {
            serverUrl: 'https://wtsdealnow.com/chat_bot/',
            containerId: 'it-solution-chat-container',
            buttonId: 'it-solution-chat-toggle',
            defaultStyles: true,
        },

        init: function(options = {}) {
            this.config = { ...this.config, ...options };
            this.injectChatContainer();
            this.injectChatToggleButton();
            this.addEventListeners();
            if (this.config.defaultStyles) {
                this.injectDefaultStyles();
            }
        },

        injectChatContainer: function() {
            const container = document.createElement('div');
            container.id = this.config.containerId;
            container.innerHTML = `
                <div class="it-solution-chat-header">
                    <h3>IT Solution Bot</h3>
                    <button id="it-solution-chat-close">&times;</button>
                </div>
                <div class="it-solution-chat-messages"></div>
                <div class="it-solution-chat-input-area">
                    <input type="text" id="it-solution-chat-input" placeholder="Type your message...">
                    <button id="it-solution-chat-send">Send</button>
                    <button id="it-solution-voice-input"><i class='bx bxs-microphone-alt'></i></button>
                </div>
            `;
            container.classList.add('it-solution-chat-container', 'hidden');
            document.body.appendChild(container);
        },

        injectChatToggleButton: function() {
            const button = document.createElement('button');
            button.id = this.config.buttonId;
            button.textContent = '💬 Chat';
            button.classList.add('it-solution-chat-toggle');
            document.body.appendChild(button);
        },

        addEventListeners: function() {
            const container = document.getElementById(this.config.containerId);
            const toggleButton = document.getElementById(this.config.buttonId);
            const closeButton = document.getElementById('it-solution-chat-close');
            const sendButton = document.getElementById('it-solution-chat-send');
            const inputField = document.getElementById('it-solution-chat-input');
            const voiceButton = document.getElementById('it-solution-voice-input');

            // Send message function, making it available globally in the SDK object
            this.sendMessage = () => {
                const message = inputField.value.trim();
                if (message) {
                    this.addMessage(message, 'user');
                    this.sendMessageToServer(message);
                    inputField.value = '';
                }
            };

            // Toggle chat visibility
            toggleButton.addEventListener('click', () => {
                container.classList.toggle('hidden');
            });

            // Close chat
            closeButton.addEventListener('click', () => {
                container.classList.add('hidden');
            });

            // Send message on button click or pressing Enter
            sendButton.addEventListener('click', this.sendMessage);
            inputField.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.sendMessage();
            });

            // Handle voice input
            voiceButton.addEventListener('click', () => {
                this.startVoiceRecognition();
            });
        },

        addMessage: function(message, sender) {
            const messagesContainer = document.querySelector('.it-solution-chat-messages');
            const messageElement = document.createElement('div');
            messageElement.classList.add('it-solution-message', `it-solution-${sender}-message`);
            messageElement.innerHTML = message;
            messagesContainer.appendChild(messageElement);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        },

        sendMessageToServer: function(message) {
            fetch(this.config.serverUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            })
            .then(response => response.json())
            .then(data => {
                console.log("data", data)
                
                // Check if the response is a download URL
                if (data.startsWith('/download_report/')) {
                    const downloadLink = `<a href="${data}" target="_blank">Click here to download report</a>`;
                    this.addMessage(downloadLink, 'bot');
                } else {
                    // Regular bot response
                    this.addMessage(data, 'bot');   
                    this.speakMessage(data);
                }
            })
            .catch(error => {
                this.addMessage('Sorry, there was an error processing your message.', 'bot');
            });
        },

        startVoiceRecognition: function() {
            const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.lang = 'en-US';
            recognition.start();

            recognition.onresult = (event) => {
                const voiceMessage = event.results[0][0].transcript;
                document.getElementById('it-solution-chat-input').value = voiceMessage;
                
                // Automatically send the message after voice recognition
                this.sendMessage();
            };

            recognition.onerror = () => {
                this.addMessage('Sorry, I could not understand your speech.', 'bot');
            };
        },

        speakMessage: function(text) {
            const utterance = new SpeechSynthesisUtterance(text);
            speechSynthesis.speak(utterance);
        },

        injectDefaultStyles: function() {
            const style = document.createElement('style');
            style.textContent = `
                .it-solution-chat-container {
                    position: fixed !important;
                    bottom: 20px !important;
                    right: 20px !important;
                    width: 350px !important;
                    border: 1px solid #ccc !important;
                    background: white !important;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1) !important;
                    border-radius: 8px !important;
                    z-index: 2005 !important;
                }
                .it-solution-chat-container.hidden {
                    display: none !important;
                }
                #it-solution-chat-send {
                    border: 0 !important;
                    background: lightgreen !important;
                    padding: 0px 10px !important;
                    border-radius: 5px !important;
                }
                #it-solution-voice-input {
                    margin-left: 5px !important;
                    border: 0 !important;
                    background: lightblue !important;
                    padding: 0px 10px !important;
                    border-radius: 5px !important;
                }
                .it-solution-chat-header {
                    background: #a5a6ff !important;
                    padding: 10px !important;
                    display: flex !important;
                    justify-content: space-between !important;
                    align-items: center !important;
                    color: #fff !important;
                    margin: 0 !important;
                }
                .it-solution-chat-header h3 {
                    color: #fff !important;
                    margin: 0 !important;
                    font-size: 20px !important;
                }
                #it-solution-chat-close {
                    background: #ff0000 !important;
                    padding: 0px 9px !important;
                    border-radius: 50% !important;
                    border: none !important;
                    color: wheat !important;
                    font-size: 20px !important;
                }
                .it-solution-chat-messages {
                    height: 400px !important;
                    overflow-y: auto !important;
                    padding: 10px !important;
                }
                .it-solution-message {
                    margin-bottom: 10px !important;
                    padding: 10px !important;
                    border-radius: 5px !important;
                }
                .it-solution-user-message {
                    background: #e6f2ff !important;
                    text-align: right !important;
                }
                .it-solution-bot-message {
                    background: #f0f0f0 !important;
                }
                .it-solution-chat-input-area {
                    display: flex !important;
                    padding: 10px !important;
                    border-top: 1px solid #ccc !important;
                }
                .it-solution-chat-input-area input {
                    flex-grow: 1 !important;
                    margin-right: 10px !important;
                    padding: 5px !important;
                }
                .it-solution-chat-toggle {
                    position: fixed !important;
                    bottom: 20px !important;
                    right: 20px !important;
                    background: #007bff !important;
                    color: white !important;
                    border: none !important;
                    padding: 10px 15px !important;
                    border-radius: 50px !important;
                    cursor: pointer !important;
                    z-index: 1001 !important;
                }
            `;
    document.head.appendChild(style);

        }
    };

    if (window.ITSolutionChatConfig) {
        window.ITSolutionChatSDK.init(window.ITSolutionChatConfig);
    }
})();
