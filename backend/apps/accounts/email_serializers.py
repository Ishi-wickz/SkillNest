from rest_framework import serializers


class EmailOnlySerializer(serializers.Serializer):
    email = serializers.EmailField()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=500)


class ResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=50)
    token = serializers.CharField(max_length=200)
    password = serializers.CharField(write_only=True, max_length=128)