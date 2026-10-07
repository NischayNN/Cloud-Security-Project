"""API/collector tests must never open or reset the user's persistent database."""
import os

os.environ["CLOUD_SECURITY_STORE"] = "memory"
