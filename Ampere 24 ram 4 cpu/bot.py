import oci
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Setup configuration from environment variables
config = {
    "user": os.getenv("OCI_USER_ID") or os.getenv("OCI_USER_OCID"),
    "key_content": os.getenv("OCI_PRIVATE_KEY") or os.getenv("OCI_API_PRIVATE_KEY"),
    "fingerprint": os.getenv("OCI_FINGERPRINT"),
    "tenancy": os.getenv("OCI_TENANCY_ID") or os.getenv("OCI_TENANCY_OCID"),
    "region": os.getenv("OCI_REGION", "eu-frankfurt-1")
}

try:
    compute_client = oci.core.ComputeClient(config)
    identity_client = oci.identity.IdentityClient(config)
    print("OCI Authentication Successful. Initializing loop sequence...")
except Exception as e:
    print(f"Authentication Failed: {e}")
    exit(1)

# Execution parameters
compartment_id = os.getenv("OCI_COMPARTMENT_OCID") or os.getenv("OCI_TENANCY_ID") or os.getenv("OCI_TENANCY_OCID")
subnet_id = os.getenv("OCI_SUBNET_ID")
image_id = os.getenv("OCI_IMAGE_ID")
public_ssh_key = os.getenv("OCI_PUBLIC_SSH_KEY") or os.getenv("OCI_SSH_PUBLIC_KEY")

# SAFETY CHECKS
if not public_ssh_key or public_ssh_key.strip() == "":
    print("CRITICAL ERROR: SSH public key is empty or missing from your secrets!")
    exit(1)

if not subnet_id or not subnet_id.startswith("ocid1.subnet"):
    print("CRITICAL ERROR: OCI_SUBNET_ID is missing or invalid!")
    exit(1)

if not image_id or not image_id.startswith("ocid1.image"):
    print("CRITICAL ERROR: OCI_IMAGE_ID is missing or invalid!")
    exit(1)

# Dynamically fetch Availability Domains from your account
try:
    ad_response = identity_client.list_availability_domains(compartment_id=config["tenancy"])
    ads = [ad.name for ad in ad_response.data]
    print(f"Detected Availability Domains: {ads}")
except Exception as e:
    print(f"Failed to fetch Availability Domains automatically: {e}")
    ads = ["SbZQ:EU-FRANKFURT-1-AD-1", "SbZQ:EU-FRANKFURT-1-AD-2", "SbZQ:EU-FRANKFURT-1-AD-3"]

total_attempts = 60 

for i in range(1, total_attempts + 1):
    current_ad = ads[(i - 1) % len(ads)]
    print(f"[Attempt {i}/{total_attempts}] Requesting instance in {current_ad}...")
    
    try:
        request = oci.core.models.LaunchInstanceDetails(
            display_name="FX-Backend-Server",
            compartment_id=compartment_id,
            availability_domain=current_ad,
            shape="VM.Standard.A1.Flex",
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=2,
                memory_in_gbs=12
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=image_id,
                boot_volume_size_in_gbs=100
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet_id,
                assign_public_ip=True,
                assign_private_dns_record=True,
                display_name="forexalertsvnic"
            ),
            metadata={
                "ssh_authorized_keys": str(public_ssh_key).strip()
            }
        )
        
        response = compute_client.launch_instance(request)
        if response.status == 200:
            print("SUCCESS! Authorized Server creation initialized perfectly.")
            exit(0)
            
    except oci.exceptions.ServiceError as e:
        if "Out of host capacity" in str(e) or e.status == 500:
            print(f"-> Capacity Unavailable. Resting 60 seconds...")
        else:
            print(f"-> API Error: {e.message}")
            
    if i < total_attempts:
        time.sleep(60)
