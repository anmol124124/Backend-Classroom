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
            const { meetingId, token, container, onLeave } = options;

            if (!meetingId || !token || !container) {
                console.error('MeetingSDK Error: meetingId, token, and container are required.');
                return;
            }

            const containerElement = document.querySelector(container);
            if (!containerElement) {
                console.error(`MeetingSDK Error: Container "${container}" not found.`);
                return;
            }

            // Meeting service backend URL
            const BACKEND_URL = "http://localhost:8000";

            // Construct the meeting room URL with token and embedded flag
            const meetingUrl = `${BACKEND_URL}/meeting/${meetingId}?token=${token}&embedded=true`;

            // Create and configure the iframe
            const iframe = document.createElement('iframe');
            iframe.src = meetingUrl;
            iframe.style.width = '100%';
            iframe.style.height = '100%';
            iframe.style.minHeight = '500px';
            iframe.style.border = 'none';

            // Critical permissions for WebRTC inside iframes
            iframe.allow = "camera; microphone; display-capture; fullscreen; autoplay";
            iframe.setAttribute("allowfullscreen", "true");

            // Security sandbox with necessary permissions
            iframe.setAttribute("sandbox", "allow-same-origin allow-scripts allow-forms allow-popups allow-modals allow-downloads");

            // Clear container and append iframe
            containerElement.innerHTML = '';
            containerElement.appendChild(iframe);

            // Handle messages from the iframe (e.g., when the user leaves)
            const messageHandler = function (event) {
                if (event.data && event.data.type === 'meeting-ended') {
                    console.log('MeetingSDK: Meeting ended.');
                    if (typeof onLeave === 'function') {
                        onLeave();
                    }
                    window.removeEventListener('message', messageHandler);
                }
            };
            window.addEventListener('message', messageHandler);

            console.log(`MeetingSDK: Joined room ${meetingId} in container ${container}`);
        }
    };

    // Expose the SDK globally
    window.MeetingSDK = MeetingSDK;
})();
