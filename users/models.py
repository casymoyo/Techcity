"""
This module manages user models and related functionality, including:

* **User extension:** Customizes the built-in Django User model to include store association, unique codes, phone numbers, and role fields.
* **User Roles:** Defines distinct user roles ('Admin', 'Accountant', 'Salesperson') for role-based access.
* **Group Creation:** Integration with Django's auth system, automatically creating default groups during migrations.
* **Code Generation:** Implements logic to generate random unique codes for each user. 
"""

import random, string
from django.db import models
from django.apps import apps
from company.models import Branch
from django.contrib.auth.models import AbstractUser, Group
from django.db.models.signals import post_migrate, post_save

ADMIN_GROUP_NAME = 'Admin'
ACCOUNTANT_GROUP_NAME = 'Accountant'
SALESPERSON_GROUP_NAME = 'Salesperson'

from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager with extra functionalities.
    """

    def create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given email, password and extra fields.
        If the first user created, grant them superuser and (optionally) admin group access.
        """
        if not email:
            raise ValueError('The Email field is required')
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.is_staff = True
        user.save(using=self._db)

        if self.model.objects.count() == 1:
            user.is_superuser = True
            user.groups.add(Group.objects.get_or_create(name='Admin')[0])
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Creates and saves a SuperUser with the given email, password and extra fields.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is False:
            raise ValueError('Superuser must have is_staff=True.')

        if extra_fields.get('is_superuser') is False:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    USER_ROLES = (
        ('Owner', 'Owner'),
        ('Admin', 'Admin'),
        ('sales', 'Salesperson'),
        ('accountant', 'Accountant')
    )
    email = models.EmailField(unique=True)
    profile_image = models.ImageField(upload_to='Profile_images', blank=True, null=True)
    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, null=True, blank=True)
    branch = models.ForeignKey('company.Branch', on_delete=models.CASCADE, null=True, blank=True)
    # todo remove user code and groups
    code = models.CharField(max_length=50, null=True, blank=True)
    groups = models.ManyToManyField(Group)

    phonenumber = models.CharField(max_length=13)
    role = models.CharField(choices=USER_ROLES, max_length=50)

    def code_generator(self) -> str:
        length = 5
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(length))
            if not User.objects.filter(code=code).exists():
                return code

    def save(self, *args, **kwargs):
        # todo remove self.code and signals
        if not self.code:
            self.code = self.code_generator()
        super().save(*args, **kwargs)

        # validate that the user's branch is associated with the same company
        if self.branch and self.company and self.branch.company != self.company:
            raise ValueError('The branch does not belong to the specified company')

    def __str__(self) -> str:
        return self.username

    objects = CustomUserManager()


def assign_admin_group(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        admin_group = Group.objects.get(name=ADMIN_GROUP_NAME)
        instance.groups.add(admin_group)


def create_groups(sender, **kwargs):
    Group.objects.get_or_create(name=ADMIN_GROUP_NAME)
    Group.objects.get_or_create(name=ACCOUNTANT_GROUP_NAME)
    Group.objects.get_or_create(name=SALESPERSON_GROUP_NAME)


post_save.connect(assign_admin_group, sender=User)
post_migrate.connect(create_groups, sender=apps.get_app_config('users'))
