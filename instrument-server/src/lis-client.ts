import axios from 'axios';
import type { LabResult } from './parser';

const API_URL = process.env.LIS_API_URL || 'http://localhost:3000/api';
const USERNAME = process.env.LIS_USERNAME || 'admin';
const PASSWORD = process.env.LIS_PASSWORD || 'admin123';

let authToken: string | null = null;

async function login() {
    try {
        console.log(`Authenticating with LIS at ${API_URL}...`);
        const res = await axios.post(`${API_URL}/auth/login`, {
            username: USERNAME,
            password: PASSWORD
        });

        // Extract cookie from response headers if possible, or just ignore if relying on specialized stateless API
        // But our API uses cookies. Axios handles cookies automatically if configured with jar, 
        // or we need to extract 'set-cookie'.
        const cookies = res.headers['set-cookie'];
        if (cookies) {
            authToken = cookies.join('; ');
            console.log('Login successful. Session obtained.');
        }
    } catch (error: any) {
        console.error('Login failed:', error.message);
    }
}

export async function pushResults(results: LabResult[]) {
    if (!authToken) await login();

    for (const result of results) {
        try {
            // We need a specific endpoint to receive machine results.
            // Using /api/results/ingest (we need to build this!) or piggybacking on POST /api/results
            // Let's assume we post to /api/results with a specific payload.

            console.log(`Pushing result ${result.testCode} = ${result.value} for ${result.accessionNumber}...`);

            await axios.post(`${API_URL}/results/ingest`, {
                accessionNumber: result.accessionNumber,
                testCode: result.testCode,
                value: result.value,
                units: result.units,
                flags: result.flags,
                timestamp: result.timestamp
            }, {
                headers: {
                    Cookie: authToken
                }
            });
            console.log('Success.');
        } catch (error: any) {
            console.error(`Failed to push result: ${error.message}`);
            if (error.response?.status === 401) {
                authToken = null; // Retry login next time
            }
        }
    }
}
