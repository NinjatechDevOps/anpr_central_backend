"""
Report Service - Generate CSV/Excel reports for detections.
"""
from typing import List, Optional
from io import StringIO
import csv
from datetime import datetime, timedelta

from app.models.anpr_detection import AnprDetection


class ReportService:
    """Service for generating detection reports."""

    @staticmethod
    def generate_csv(detections: List[AnprDetection], timezone_offset_minutes: Optional[int] = 0) -> str:
        """
        Generate CSV report from detections.

        Args:
            detections: List of AnprDetection objects
            timezone_offset_minutes: Timezone offset in minutes from UTC (e.g., 330 for IST UTC+5:30, -300 for EST UTC-5:00)

        Returns:
            CSV content as string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Write headers - separated date and time columns for both client and server
        writer.writerow([
            'Client Detection Date',
            'Client Detection Time',
            'Server Received Date',
            'Server Received Time',
            'Detection ID',
            'Organization Name',
            'Camera ID',
            'Camera Name',
            'Object Type',
            'Activity Type',
            'Image URL',
            'Numberplate Available',
            'Numberplate Color',
            'Vehicle Side'
        ])

        # Calculate timezone offset
        tz_offset = timedelta(minutes=timezone_offset_minutes)

        # Write data rows
        for d in detections:
            try:
                # Format client detection datetime (if available)
                client_date = ''
                client_time = ''
                if d.detected_at:
                    # Convert UTC to user's local timezone
                    local_dt = d.detected_at + tz_offset
                    client_date = local_dt.strftime('%d/%m/%Y')
                    client_time = local_dt.strftime('%I:%M:%S %p')

                # Format server received datetime
                server_date = ''
                server_time = ''
                if d.created_at:
                    # Convert UTC to user's local timezone
                    local_dt = d.created_at + tz_offset
                    server_date = local_dt.strftime('%d/%m/%Y')
                    server_time = local_dt.strftime('%I:%M:%S %p')

                writer.writerow([
                    client_date,
                    client_time,
                    server_date,
                    server_time,
                    d.id,
                    d.organization.name if d.organization else '',
                    d.camera_id,
                    d.camera_name or '',
                    d.vehicle_class or '',
                    d.activity_type or '',
                    f"/uploads/{d.image_path}" if d.image_path else '',
                    'Yes' if d.numberplate_available else 'No',
                    d.numberplate_color.value if d.numberplate_color else '',
                    d.vehicle_side.value if d.vehicle_side else ''
                ])
            except Exception as e:
                # Log error but continue processing
                print(f"Error writing row for detection {d.id}: {e}")
                continue

        return output.getvalue()

    @staticmethod
    def generate_filename() -> str:
        """Generate timestamped filename for report."""
        return f"detections_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
