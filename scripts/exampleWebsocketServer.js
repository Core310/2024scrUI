const WebSocket = require('ws');
const server = new WebSocket.Server({port: 8080});
server.on('connection', (ws) => {
    console.log('Client connected');

    const sendData = () => {
        let deviceState = JSON.stringify({
            op: 'data',
            topic: "/scr/state/system",//TODO NOT WORKING WHEN TRYING TO PORT TO GLOBALS.JS VARIABLES
            timestamp: new Date().toISOString(),
            device: 'autonav',
            state: '0'
        });

        let logging = JSON.stringify({//todo, not sure what to put for example data here
            op: 'data',
            topic: '/scr/logging',
            timestamp: new Date().toISOString(),
            data: 'data:image/jpeg;base64,',
            node: 'autonav'
        });
        let imgData = 'https://www.greenlaundry.net/blog/wp-content/uploads/2011/11/animalsintrees-1.gif';

        let conbus = JSON.stringify({
            op: 'data',
            topic: '/autonav/conbus',
            timestamp: new Date().toISOString(),
            id: 0,
            data: imgData
        });

        let combined = JSON.stringify({
            op: 'data',
            topic: '/autonav/cfg_space/combined/image',
            timestamp: new Date().toISOString(),
            data: 'data:image/jpeg;base64,'
        });

        let leftSmall = JSON.stringify({
            op: 'data',
            topic: '/autonav/cfg_space/raw/image/left_small',
            timestamp: new Date().toISOString(),
            data: imgData
        });

        let rightSmall = JSON.stringify({
            op: 'data',
            topic: '/autonav/cfg_space/raw/image/right_small',
            timestamp: new Date().toISOString(),
            data: imgData
        });

        let compressedRight = JSON.stringify({
            op: 'data',
            topic: '/autonav/camera/compressed/right',
            timestamp: new Date().toISOString(),
            data: imgData
        });

        let compressedLeft = JSON.stringify({
            op: 'data',
            topic: '/autonav/camera/compressed/left',
            timestamp: new Date().toISOString(),
            data: imgData
        });

        let imuData = JSON.stringify({
            op: 'data',
            topic: '/autonav/imu',
            timestamp: new Date().toISOString(),
            accel_x: Math.random() * 10,
            accel_y: Math.random() * 10,
            accel_z: Math.random() * 10,
            angular_x: Math.random() * 10,
            angular_y: Math.random() * 10,
            angular_z: Math.random() * 10,
            yaw: Math.random() * 10,
            pitch: Math.random() * 10,
            roll: Math.random() * 10
        });

        let positionData = JSON.stringify({
            op: 'data',
            topic: '/autonav/position',
            timestamp: new Date().toISOString(),
            x: Math.random() * 10,
            y: Math.random() * 10,
            theta: Math.random() * 10,
            latitude: Math.random() * 10,
            longitude: Math.random() * 10
        });

        let motorFeedbackData = JSON.stringify({
            op: 'data',
            topic: '/autonav/MotorFeedback',
            timestamp: new Date().toISOString(),
            delta_x: Math.random() * 10,
            delta_y: Math.random() * 10,
            delta_theta: Math.random() * 10
        });

        let gpsData = JSON.stringify({
            //                    const {latitude, longitude, gps_fix, is_locked, satellites} = msg;
            op: 'data',
            topic: '/autonav/gps',
            timestamp: new Date().toISOString(),
            latitude: Math.random() * 10,
            longitude: Math.random() * 10,
            gps_fix: Math.random() * 10,
            is_locked: true,
            satellites: Math.random() * 10//todo is this correct?
        });

        let sysState = JSON.stringify({
            op: 'data',
            topic: '/scr/state/system',
            timestamp: new Date().toISOString(),
            state: '0',
            mode: 'autonomous',
            mobility: 'mobile'
        });

        let motorInput = JSON.stringify({
            op: 'data',
            topic: '/autonav/MotorInput',
            timestamp: new Date().toISOString(),
            forward_velocity: Math.random() * 10,
            angular_velocity: Math.random() * 10
        });
        ws.send(deviceState);
        ws.send(logging);
        ws.send(conbus);
        setInterval(() => {
            ws.send(combined);
            ws.send(leftSmall);
            ws.send(rightSmall);
            ws.send(compressedRight);
            ws.send(compressedLeft);
        }, 500);
        ws.send(imuData);
        ws.send(positionData);
        ws.send(motorFeedbackData);
        ws.send(gpsData);
        ws.send(sysState);
        ws.send(motorInput);
    };
    // Send data every second
    const interval = setInterval(sendData, 1000);

    ws.on('close', () => {
        console.log('Client disconnected');
        clearInterval(interval);
    });

    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        clearInterval(interval);
    });
});


console.log('WebSocket server is running on ws://localhost:8080');