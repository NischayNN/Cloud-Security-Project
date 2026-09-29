"""Fake CloudTrail records (same shape as real ones) so we can develop without AWS."""
import json


def _rec(n, name, source, params, user="student-dev", ip="203.0.113.10"):
    return {"eventID": f"evt-{n:04d}", "eventName": name, "eventSource": source,
            "eventTime": f"2026-09-2{n}T10:00:00Z", "awsRegion": "ap-south-1",
            "recipientAccountId": "123456789012", "sourceIPAddress": ip,
            "userIdentity": {"type": "IAMUser", "userName": user}, "requestParameters": params}


def _acl(bucket, perm):
    return {"bucketName": bucket, "AccessControlPolicy": {"AccessControlList": {"Grant": [
        {"Grantee": {"URI": "http://acs.amazonaws.com/groups/global/AllUsers"}, "Permission": perm}]}}}


def _sg(gid, name, frm, to, cidr, proto="tcp"):
    return {"groupId": gid, "groupName": name, "ipPermissions": {"items": [
        {"ipProtocol": proto, "fromPort": frm, "toPort": to, "ipRanges": {"items": [{"cidrIp": cidr}]}}]}}


SAMPLE_EVENTS = [
    _rec(1, "PutBucketAcl", "s3.amazonaws.com", _acl("college-notes", "READ")),                 # Medium
    _rec(2, "PutBucketAcl", "s3.amazonaws.com", _acl("prod-customer-backup", "WRITE")),         # Critical
    _rec(3, "AttachUserPolicy", "iam.amazonaws.com",
         {"userName": "intern-ravi", "policyArn": "arn:aws:iam::aws:policy/AdministratorAccess"}),  # Critical
    _rec(4, "PutUserPolicy", "iam.amazonaws.com", {"userName": "app-user", "policyName": "s3all",
         "policyDocument": json.dumps({"Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]})}),  # High
    _rec(5, "AuthorizeSecurityGroupIngress", "ec2.amazonaws.com", _sg("sg-0a1b2c", "prod-web", 22, 22, "0.0.0.0/0")),  # Critical
    _rec(6, "AuthorizeSecurityGroupIngress", "ec2.amazonaws.com", _sg("sg-0d4e5f", "dev-sandbox", 22, 22, "0.0.0.0/0")),  # Low
    _rec(7, "AuthorizeSecurityGroupIngress", "ec2.amazonaws.com", _sg("sg-0g7h8i", "web", 443, 443, "0.0.0.0/0")),  # no incident
]
