from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import User, UserAddress
from app.barbers.models import Favorite, LastViewed
from django.db.models import F


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("full_name", "first_name", "last_name", "email", "password", "gender", "phone")

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        first = validated_data.pop("first_name", "").strip()
        last = validated_data.pop("last_name", "").strip()
        if not validated_data.get("full_name"):
            validated_data["full_name"] = (first + " " + last).strip()
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        if email and password:
            user = authenticate(request=self.context.get("request"), email=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid email or password.")
        else:
            raise serializers.ValidationError("Must include email and password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    favorites = serializers.ListField(child=serializers.IntegerField(), source='favorites_ids', read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone", "gender", "date_joined", "favorites")
        read_only_fields = ("id", "date_joined", "favorites")

    


class UserUpdateSerializer(serializers.ModelSerializer):
    add_favorite_barbershop = serializers.IntegerField(required=False)
    remove_favorite_barbershop = serializers.IntegerField(required=False)

    class Meta:
        model = User
        fields = ("full_name", "add_favorite_barbershop", "remove_favorite_barbershop")

    def update(self, instance, validated_data):
        # Update basic fields
        full_name = validated_data.get("full_name")
        if full_name is not None:
            instance.full_name = full_name
            instance.save(update_fields=["full_name"])

        # Favorite mutations on JSON list plus counters
        from app.barbers.models import Barbershop
        add_id = validated_data.get("add_favorite_barbershop")
        if add_id is not None:
            ids = list(instance.favorites_ids or [])
            if add_id not in ids:
                ids.append(add_id)
                instance.favorites_ids = ids
                instance.save(update_fields=["favorites_ids"])
                Barbershop.objects.filter(id=add_id).update(favorites_count=F('favorites_count') + 1)

        remove_id = validated_data.get("remove_favorite_barbershop")
        if remove_id is not None:
            ids = list(instance.favorites_ids or [])
            if remove_id in ids:
                ids.remove(remove_id)
                instance.favorites_ids = ids
                instance.save(update_fields=["favorites_ids"])
                Barbershop.objects.filter(id=remove_id).update(favorites_count=F('favorites_count') - 1)

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ("id", "city", "district", "latitude", "longitude", "is_default", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class FavoriteSerializer(serializers.ModelSerializer):
    barbershop_name = serializers.CharField(source='barbershop.name', read_only=True)
    barbershop_address = serializers.CharField(source='barbershop.address', read_only=True)
    barbershop_rating = serializers.FloatField(source='barbershop.rating_avg', read_only=True)
    barbershop_image = serializers.CharField(source='barbershop.main_image', read_only=True)

    class Meta:
        model = Favorite
        fields = ("id", "barbershop", "barbershop_name", "barbershop_address", "barbershop_rating", "barbershop_image", "created_at")
        read_only_fields = ("id", "created_at")


class LastViewedSerializer(serializers.ModelSerializer):
    barbershop_name = serializers.CharField(source='barbershop.name', read_only=True)
    barbershop_address = serializers.CharField(source='barbershop.address', read_only=True)
    barbershop_rating = serializers.FloatField(source='barbershop.rating_avg', read_only=True)
    barbershop_image = serializers.CharField(source='barbershop.main_image', read_only=True)

    class Meta:
        model = LastViewed
        fields = ("id", "barbershop", "barbershop_name", "barbershop_address", "barbershop_rating", "barbershop_image", "viewed_at")
        read_only_fields = ("id", "viewed_at")


