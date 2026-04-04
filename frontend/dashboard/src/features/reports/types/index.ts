export type ReportFormat = 'json' | 'csv' | 'pdf';
export type ReportStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface DateRange {
    start: string;
    end: string;
}

export interface ReportRequest {
    locomotive_id: string | null;
    report_type: string;
    format: ReportFormat;
    date_range: DateRange;
}

export interface ReportResponse {
    report_id: string;
    locomotive_id: string | null;
    report_type: string;
    format: ReportFormat;
    status: ReportStatus;
    created_at: string;
    data: unknown;
}

export interface ReportsQuery {
    locomotive_id?: string;
    status?: ReportStatus;
    offset?: number;
    limit?: number;
}
