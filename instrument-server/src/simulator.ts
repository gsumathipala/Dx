import net from 'net';

const PORT = 6000;
const HOST = 'localhost';

const START_BLOCK = 0x0B;
const END_BLOCK_1 = 0x1C;
const END_BLOCK_2 = 0x0D;

// Sample HL7 ORU^R01 Message
// MSH: Header
// PID: Patient (Test Patient)
// OBR: Order (Accession 20241219-01)
// OBX: Result (GLU = 105 mg/dL)
const hl7Message = `MSH|^~\\&|ANALYZER|LAB|LIS|LAB|${new Date().toISOString().replace(/[-:T\.]/g, '')}||ORU^R01|MSG00001|P|2.5
PID|1||12345^^^MRN||DOE^JOHN^||19800101|M
OBR|1||ACC-TEST-001|BASIC_PANEL|||20241219000000
OBX|1|NM|GLU^Glucose||105|mg/dL|70-100|H|||F
OBX|2|NM|CRE^Creatinine||0.9|mg/dL|0.7-1.3|N|||F`;

// Wrap in MLLP
const payload = Buffer.concat([
    Buffer.from([START_BLOCK]),
    Buffer.from(hl7Message.replace(/\n/g, '\r')), // HL7 uses \r delimiter
    Buffer.from([END_BLOCK_1, END_BLOCK_2])
]);

const client = new net.Socket();

client.connect(PORT, HOST, () => {
    console.log('Connected to Middleware');
    client.write(payload);
    console.log('Sent HL7 Message');
});

client.on('data', (data) => {
    // Ack received?
    const str = data.toString();
    if (str.includes('ACK')) {
        console.log('Received ACK from Middleware');
    } else {
        console.log('Received data:', str);
    }
    client.destroy();
});

client.on('close', () => {
    console.log('Connection closed');
});
