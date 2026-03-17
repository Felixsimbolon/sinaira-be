from datetime import datetime

from rest_framework import serializers


class TherapistPerformanceSummaryQuerySerializer(serializers.Serializer):
    startDate = serializers.CharField(required=True)
    endDate = serializers.CharField(required=True)

    def validate(self, attrs):
        start_raw = attrs.get("startDate")
        end_raw = attrs.get("endDate")

        try:
            start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                {"startDate": "Format startDate tidak valid. Gunakan YYYY-MM-DD."}
            )

        try:
            end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                {"endDate": "Format endDate tidak valid. Gunakan YYYY-MM-DD."}
            )

        if start_date > end_date:
            raise serializers.ValidationError(
                {"dateRange": "startDate tidak boleh lebih besar dari endDate."}
            )

        attrs["start_date"] = start_date
        attrs["end_date"] = end_date
        return attrs
