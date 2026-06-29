import net from 'net';
import { parseHL7 } from './parser';
import { pushResults } from './lis-client';

const PORT = 6000;
const START_BLOCK = 0x0B;
const END_BLOCK_1 = 0x1C;
const END_BLOCK_2 = 0x0D;

const server = net.createServer((socket) => {
    console.log(`Client connected: ${socket.remoteAddress}`);

    let buffer = Buffer.alloc(0);

    socket.on('data', async (chunk) => {
        buffer = Buffer.concat([buffer, chunk]);

        // Check for MLLP framing
        let startIdx = buffer.indexOf(START_BLOCK);
        let endIdx = buffer.indexOf(END_BLOCK_1);

        while (startIdx !== -1 && endIdx !== -1) {
            if (endIdx > startIdx) {
                // Extract message (excluding wrappers)
                const rawMessage = buffer.subarray(startIdx + 1, endIdx).toString('utf-8');
                console.log('Received HL7 Message (' + rawMessage.length + ' chars)');

                // Process
                try {
                    const results = parseHL7(rawMessage);
                    console.log(`Parsed ${results.length} results.`);
                    await pushResults(results);

                    // Send ACK (Simple positive ACK)
                    const ack = `MSH|^~\\&|LIS||INSTRUMENT||${new Date().toISOString().replace(/[-:T\.]/g, '')}||ACK|1|P|2.5\rMSA|AA|1\r`;
                    const response = Buffer.concat([
                        Buffer.from([START_BLOCK]),
                        Buffer.from(ack),
                        Buffer.from([END_BLOCK_1, END_BLOCK_2])
                    ]);
                    socket.write(response);
                } catch (e) {
                    console.error('Processing failed:', e);
                }

                // Remove processed part from buffer
                buffer = buffer.subarray(endIdx + 2); // +2 to skip 0x1C 0x0D
            } else {
                // Malformed or fragmented? reset
                buffer = buffer.subarray(startIdx + 1);
            }

            // Look for next
            startIdx = buffer.indexOf(START_BLOCK);
            endIdx = buffer.indexOf(END_BLOCK_1);
        }
    });

    socket.on('error', (err) => {
        console.error('Socket error:', err.message);
    });

    socket.on('close', () => {
        console.log('Client disconnected');
    });
});

server.listen(PORT, () => {
    console.log(`Instrument Middleware listening on port ${PORT}`);
});
