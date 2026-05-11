-- Add new columns to daily_recommendations
ALTER TABLE daily_recommendations ADD COLUMN status TEXT DEFAULT 'Approved';
ALTER TABLE daily_recommendations ADD COLUMN emailed INTEGER DEFAULT 0;
ALTER TABLE daily_recommendations ADD COLUMN email_error TEXT;
ALTER TABLE daily_recommendations ADD COLUMN dispatched_at TIMESTAMP;

-- Create indices for the new querying fields
CREATE INDEX IF NOT EXISTS idx_rec_status ON daily_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_rec_emailed ON daily_recommendations(emailed);

-- Create email audit log table
CREATE TABLE IF NOT EXISTS email_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER NOT NULL,
    recipient_email TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_email_audit_rec_id ON email_audit_log(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_email_audit_email ON email_audit_log(recipient_email);
