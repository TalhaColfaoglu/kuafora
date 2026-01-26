from rest_framework import serializers
from app.analytics.models import AppEvent, ScreenView, FeatureUsage, UserSession


class AppEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppEvent
        fields = [
            'event_type', 'app_type', 'session_id', 'device_id',
            'platform', 'app_version', 'os_version', 'timestamp',
            'ip_address', 'user_agent'
        ]
        read_only_fields = ['timestamp']


class ScreenViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreenView
        fields = [
            'screen_name', 'app_type', 'session_id', 'device_id',
            'view_duration', 'timestamp', 'metadata'
        ]
        read_only_fields = ['timestamp']


class FeatureUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureUsage
        fields = [
            'feature_type', 'app_type', 'session_id', 'device_id',
            'timestamp', 'metadata', 'success'
        ]
        read_only_fields = ['timestamp']


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = [
            'session_id', 'device_id', 'app_type', 'platform',
            'app_version', 'os_version', 'start_time', 'end_time',
            'duration', 'screen_count', 'event_count', 'ip_address', 'user_agent'
        ]
        read_only_fields = ['start_time', 'duration', 'screen_count', 'event_count']


class BatchTrackingSerializer(serializers.Serializer):
    """Toplu tracking verisi gönderme için"""
    events = AppEventSerializer(many=True, required=False)
    screen_views = ScreenViewSerializer(many=True, required=False)
    feature_usages = FeatureUsageSerializer(many=True, required=False)
    session = UserSessionSerializer(required=False)

