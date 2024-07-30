"""
This module defines the core data models for our Company management application:

* **Company:**  Represents a physical or company store with associated information.
* **Branch:** Represents a branch location belonging to a company.
"""
from django.db import models


def company_logo_path(instance, filename):
    return f"{instance.name}/logos/{filename}"


class Company(models.Model):
    """
    Represents a physical or online store within the system. Companies can contain multiple branches.
    
    Attributes:
        name (str): The name of the store.
        description (str):  Optional textual description of the store.
        address (str): Optional physical address.
        domain (str):  Optional website domain associated with the store.
        logo (ImageField): Optional store logo.
        email (str): Optional contact email for the store.
        phone_number (str): Optional contact phone number.
        timezone (str):  Optional timezone of the store (for localization).
        is_active (bool): Flag to indicate if the store is currently active. 
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    logo = models.ImageField(upload_to=company_logo_path, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # change logo name before saving and folder location
        if self.logo:
            self.logo.name = f"{self.name}_logo.png"
        super(Company, self).save(*args, **kwargs)


class Branch(models.Model):
    """
    Represents a physical branch location belonging to a Store.

    Attributes:
        store (ForeignKey): The parent Store associated with the branch.
        name (str): The name of the branch.
        description (str): Optional textual description of the branch.
        address (str): Optional physical address of the branch. 
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    phonenumber = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=255, blank=True)

    def __str__(self) -> str:
        return self.name
