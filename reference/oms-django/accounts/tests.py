from django.test import TestCase

from accounts.models import User


class UserHierarchyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='pw', role=User.Role.ADMIN)
        self.manager = User.objects.create_user(
            username='manager',
            password='pw',
            role=User.Role.MANAGER,
            parent=self.admin,
        )
        self.agency = User.objects.create_user(
            username='agency',
            password='pw',
            role=User.Role.AGENCY,
            parent=self.manager,
        )
        self.seller = User.objects.create_user(
            username='seller',
            password='pw',
            role=User.Role.SELLER,
            parent=self.agency,
        )

    def test_get_descendant_ids_returns_all_children(self):
        descendants = set(self.admin.get_descendant_ids())
        self.assertEqual(descendants, {self.manager.id, self.agency.id, self.seller.id})

    def test_get_all_order_user_ids_includes_self(self):
        all_ids = set(self.manager.get_all_order_user_ids())
        self.assertEqual(all_ids, {self.manager.id, self.agency.id, self.seller.id})
