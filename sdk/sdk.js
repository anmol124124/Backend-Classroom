(function () {
    // MeetingSDK: The global object that external platforms will use
    const MeetingSDK = {
        /**
         * Joins a meeting by creating an iframe in the specified container.
         * @param {Object} options - Configuration options
         * @param {string} options.meetingId - The unique ID of the meeting room
         * @param {string} options.token - The JWT token for authentication
         * @param {string} options.container - The CSS selector for the container element
         */
        join: function (options) {
            const { roomId, container, onLeave, token } = options;

            if (!roomId || !container) {
                console.error('MeetingSDK Error: roomId and container are required.');
                return;
            }

            const containerElement = document.querySelector(container);
            if (!containerElement) {
                console.error(`MeetingSDK Error: Container "${container}" not found.`);
                return;
            }

            // Meeting service backend URL
            const BACKEND_URL = "http://localhost:8000";

            // Construct the meeting room URL
            let meetingUrl = `${BACKEND_URL}/meeting/${roomId}?embedded=true`;
            if (token) {
                meetingUrl += `&token=${token}`;
            }

            // Create and configure the iframe
            const iframe = document.createElement('iframe');
            iframe.src = meetingUrl;
            iframe.style.width = '100%';
            iframe.style.height = '100%';
            iframe.style.border = 'none';

            // Critical permissions for WebRTC inside iframes
            iframe.allow = "camera; microphone; display-capture; fullscreen; autoplay";
            iframe.setAttribute("allowfullscreen", "true");

            // Clear container and append iframe
            containerElement.innerHTML = '';
            containerElement.appendChild(iframe);

            // Handle messages from the iframe
            const messageHandler = function (event) {
                if (event.data && event.data.type === 'meeting-ended') {
                    if (typeof onLeave === 'function') {
                        onLeave();
                    }
                    window.removeEventListener('message', messageHandler);
                }
            };
            window.addEventListener('message', messageHandler);

            console.log(`MeetingSDK: Joined room ${roomId} in container ${container}`);
        }
    };

    // Expose the SDK globally
    window.MeetingSDK = MeetingSDK;
})();
