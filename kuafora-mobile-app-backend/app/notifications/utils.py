from __future__ import annotations

from typing import Iterable

from django.contrib.auth import get_user_model

from app.notifications.models import Notification
from app.barbers.models import Favorite, Barbershop, Review
from app.campaigns.models import Campaign
from app.subscriptions.models import Subscription

User = get_user_model()


def create_user_notification(
    *,
    user: User | None,
    title: str,
    body: str,
    type_: str = "system",
    reference_id: str | None = None,
) -> Notification | None:
    """
    Tek bir kullanıcı için güvenli Notification oluşturucu.
    User None ise sessizce hiçbir şey yapmaz.
    """
    if user is None:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        body=body,
        type=type_,
        reference_id=reference_id,
    )


def bulk_notify_users(
    users: Iterable[User],
    *,
    title: str,
    body: str,
    type_: str = "system",
    reference_id: str | None = None,
) -> int:
    """
    Birden fazla kullanıcıya Notification üretir.
    Dönüş: oluşturulan kayıt sayısı.
    """
    objs: list[Notification] = []
    for u in users:
        if not u:
            continue
        objs.append(
            Notification(
                user=u,
                title=title,
                body=body,
                type=type_,
                reference_id=reference_id,
            )
        )
    if not objs:
        return 0
    created = Notification.objects.bulk_create(objs)
    return len(created)


def notify_favoriters_about_campaign(barbershop: Barbershop, campaign: Campaign) -> int:
    """
    Bir kampanya için, ilgili kuaförü favorilerine eklemiş TÜM kullanıcılara bildirim gönder.
    Dönüş: kaç kullanıcıya gönderildi.
    """
    favorites = (
        Favorite.objects.filter(barbershop=barbershop)
        .select_related("user")
        .only("user__id", "user__full_name", "user__email")
    )
    users = [fav.user for fav in favorites if fav.user_id]

    if not users:
        return 0

    title = f"Favori kuaförünüzden kampanya: {barbershop.name}"
    body = f"{campaign.name} kampanyası başladı."
    return bulk_notify_users(
        users,
        title=title,
        body=body,
        type_="system",
        reference_id=str(campaign.id),
    )


def notify_shop_admins_about_subscription(subscription: Subscription, title: str, body: str) -> int:
    """
    Abonelik durum değişikliklerinde, dükkanın admin personellerine bildirim gönder.
    """
    shop = subscription.barbershop
    admins = shop.staff.filter(is_admin=True).select_related("user").only("user__id", "user__full_name", "user__email")
    users = [s.user for s in admins if getattr(s, "user_id", None)]
    return bulk_notify_users(
        users,
        title=title,
        body=body,
        type_="system",
        reference_id=str(subscription.id),
    )


def notify_shop_about_new_review(review: Review) -> int:
    """
    Yeni müşteri yorumu geldiğinde kuaför adminlerine bildirim gönder.
    """
    shop = review.barbershop
    admins = shop.staff.filter(is_admin=True).select_related("user").only("user__id", "user__full_name", "user__email")
    users = [s.user for s in admins if getattr(s, "user_id", None)]

    if not users:
        return 0

    title = f"Yeni yorum aldınız - {shop.name}"
    if review.is_anonymous:
        prefix = "Anonim bir müşteri"
    else:
        prefix = getattr(review.user, "full_name", "") or getattr(review.user, "email", "Bir müşteri")
    body = f"{prefix} {review.rating}★ puan verdi."
    return bulk_notify_users(
        users,
        title=title,
        body=body,
        type_="system",
        reference_id=str(review.id),
    )


def notify_customer_about_reply(review: Review) -> None:
    """
    Kuaför yoruma cevap yazdığında müşteriye bildirim gönder.
    Anonim yorumlarda müşteri bildirimi atılmaz.
    """
    if review.is_anonymous or not review.user_id:
        return

    title = f"{review.barbershop.name} yorumunuza cevap verdi"
    snippet = (review.reply or "").strip()
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."
    body = snippet or "Kuaförünüz yorumunuza yanıt verdi."
    create_user_notification(
        user=review.user,
        title=title,
        body=body,
        type_="reply",
        reference_id=str(review.id),
    )


def notify_shop_about_favorites_milestone(barbershop: Barbershop, milestone: int) -> int:
    """
    Favori sayısı milestone'a ulaşınca kuaför adminlerine bildirim gönder.
    Milestone'lar: 10, 25, 50, 100, 250, 500, 1000
    """
    admins = barbershop.staff.filter(is_admin=True).select_related("user").only("user__id")
    users = [s.user for s in admins if getattr(s, "user_id", None)]
    
    if not users:
        return 0
    
    title = f"🎉 {milestone} Favori Milestone!"
    body = f"{barbershop.name} {milestone} favoriye ulaştı! Harika bir başarı!"
    return bulk_notify_users(
        users,
        title=title,
        body=body,
        type_="system",
        reference_id=f"fav_{milestone}",
    )


def notify_shop_about_views_milestone(barbershop: Barbershop, milestone: int) -> int:
    """
    Görüntülenme sayısı milestone'a ulaşınca kuaför adminlerine bildirim gönder.
    Milestone'lar: 100, 250, 500, 1000, 2500, 5000, 10000
    """
    admins = barbershop.staff.filter(is_admin=True).select_related("user").only("user__id")
    users = [s.user for s in admins if getattr(s, "user_id", None)]
    
    if not users:
        return 0
    
    title = f"📊 {milestone} Görüntülenme Milestone!"
    body = f"{barbershop.name} {milestone} kez görüntülendi! Profiliniz daha fazla müşteriye ulaşıyor!"
    return bulk_notify_users(
        users,
        title=title,
        body=body,
        type_="system",
        reference_id=f"view_{milestone}",
    )


