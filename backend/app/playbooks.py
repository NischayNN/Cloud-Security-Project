"""Response playbooks: ordered steps an analyst follows for each incident type."""
from .schemas import IncidentType, PlaybookStep as S

PLAYBOOKS = {
    IncidentType.PUBLIC_S3: [
        S(title="Confirm exposure", action="Check the bucket ACL/policy and whether sensitive objects are exposed.",
          command="aws s3api get-bucket-acl --bucket <BUCKET>"),
        S(title="Block public access", action="Enable all four S3 Block Public Access settings.",
          command="aws s3api put-public-access-block --bucket <BUCKET> --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"),
        S(title="Review access logs", action="Search CloudTrail/S3 access logs for downloads by unknown IPs."),
        S(title="Document & prevent", action="Record findings; enable account-level Block Public Access."),
    ],
    IncidentType.EXCESSIVE_IAM: [
        S(title="Identify the change", action="Find who attached/created the policy and why.",
          command="aws iam list-attached-user-policies --user-name <USER>"),
        S(title="Remove excessive permissions", action="Detach the admin/wildcard policy.",
          command="aws iam detach-user-policy --user-name <USER> --policy-arn <POLICY_ARN>"),
        S(title="Review activity", action="Check CloudTrail for actions by this principal since the change."),
        S(title="Apply least privilege", action="Replace with a scoped policy; rotate access keys if misuse is suspected."),
    ],
    IncidentType.OPEN_SSH: [
        S(title="Confirm the rule", action="Inspect the security group's inbound rules.",
          command="aws ec2 describe-security-groups --group-ids <SG_ID>"),
        S(title="Remove the open rule", action="Revoke the 0.0.0.0/0 SSH ingress rule.",
          command="aws ec2 revoke-security-group-ingress --group-id <SG_ID> --protocol tcp --port 22 --cidr 0.0.0.0/0"),
        S(title="Check instances", action="Review auth logs on instances using this group for suspicious logins."),
        S(title="Restrict access", action="Allow SSH only from a trusted IP/VPN, or switch to SSM Session Manager."),
    ],
}


def get_playbook(itype: IncidentType) -> list[S]:
    return [s.model_copy() for s in PLAYBOOKS[itype]]
