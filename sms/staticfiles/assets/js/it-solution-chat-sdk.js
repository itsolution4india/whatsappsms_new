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
            messageElement.textContent = message;
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
                this.addMessage(data, 'bot');
                this.speakMessage(data);
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
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    width: 350px;
                    border: 1px solid #ccc;
                    background: white;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    border-radius: 8px;
                    z-index: 2005;
                }
                .it-solution-chat-container.hidden {
                    display: none;
                }
                #it-solution-chat-send {
                    border: 0;
                    background: lightgreen;
                    padding: 0px 10px;
                    border-radius: 5px;
                }
                #it-solution-voice-input {
                    margin-left: 5px;
                    border: 0;
                    background: lightblue;
                    padding: 0px 10px;
                    border-radius: 5px;
                }
                .it-solution-chat-header {
                    background: #a5a6ff;
                    padding: 10px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    color: #fff;
                    margin: 0;
                }
                .it-solution-chat-header h3 {
                    color: #fff;
                    margin: 0;
                    font-size: 20px;
                }
                #it-solution-chat-close {
                    background: #ff0000;
                    padding: 0px 9px;
                    border-radius: 50%;
                    border: none;
                    color: wheat;
                    font-size: 20px;
                }
                .it-solution-chat-messages {
                    height: 400px;
                    overflow-y: auto;
                    padding: 10px;
                }
                .it-solution-message {
                    margin-bottom: 10px;
                    padding: 10px;
                    border-radius: 5px;
                }
                .it-solution-user-message {
                    background: #e6f2ff;
                    text-align: right;
                }
                .it-solution-bot-message {
                    background: #f0f0f0;
                }
                .it-solution-chat-input-area {
                    display: flex;
                    padding: 10px;
                    border-top: 1px solid #ccc;
                }
                .it-solution-chat-input-area input {
                    flex-grow: 1;
                    margin-right: 10px;
                    padding: 5px;
                }
                .it-solution-chat-toggle {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    background: #007bff;
                    color: white;
                    border: none;
                    padding: 10px 15px;
                    border-radius: 50px;
                    cursor: pointer;
                    z-index: 1001;
                }
            `;
            document.head.appendChild(style);
        }
    };

    if (window.ITSolutionChatConfig) {
        window.ITSolutionChatSDK.init(window.ITSolutionChatConfig);
    }
})();
