export function formatDate(dateString: string): string {
    if (!dateString) return '';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;

    // Use UTC methods to avoid timezone shifts if the dateString is YYYY-MM-DD
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();

    return `${day}/${month}/${year}`;
}

export function formatDateTime(dateString: string): string {
    if (!dateString) return '';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;

    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

// Missing utilities restored for build compatibility

export const fuzzyMatch = (text: string, search: string) => {
    if (!search) return true;
    if (!text) return false;
    return text.toLowerCase().includes(search.toLowerCase());
};

export const generateZPLLabel = (accession: string, name: string, dob: string) => {
    return `
^XA
^FO50,50^ADN,36,20^FD${name}^FS
^FO50,100^ADN,36,20^FDDOB: ${dob}^FS
^FO50,150^BY3^BCN,100,Y,N,N^FD${accession}^FS
^XZ
    `;
};

export const logAudit = async (action: string, userId: string, details: string) => {
    // This is a stub for the legacy function signature. 
    // In Phase 5, we use direct DB inserts for audit logs.
    console.log(`[AUDIT] ${action} by ${userId}: ${details}`);
};

export const evaluateResult = (value: string, range: any): string => {
    // Simple numeric range check
    // range expected format: { min: 10, max: 20 }
    if (!range || !value) return 'Normal';

    const num = parseFloat(value);
    if (isNaN(num)) return 'Normal'; // Non-numeric results are "Normal" or manually flagged

    // Parse range if it's a string
    const min = range.min;
    const max = range.max;

    if (typeof min === 'undefined' || typeof max === 'undefined') return 'Normal';

    if (num < min) return 'Low';
    if (num > max) return 'High';
    return 'Normal';
};
