"""
s3_governance.py lambda module for S3 governance.
"""
import os
import sys
import logging
import botocore
import re
sys.path.append("../")
from utils.common import get_config, notify_email, get_aws_client,get_account_admin_email

# global variables
ROLE_NAME = os.environ['targetMgmtRole']

logger = logging.getLogger(__name__)
logger.setLevel(logging.getLevelName(os.environ.get('logLevel', 'INFO')))

def encryption_enabled(bucketName, s3, subscriberAccountId, awsRegion,adminEmail,violatorEmail):
    """This function will return whether the Bucket is encrypted or not."""
    try:
        s3.get_bucket_encryption(Bucket=bucketName)
        logger.info(f'S3 bucket: {bucketName} is already encrypted in Account number:{subscriberAccountId}')
        return True
    except botocore.exceptions.ClientError as error:
        if 'ServerSideEncryptionConfigurationNotFoundError' in str(error):
            return False
        else:
            logger.error(f'Bucket {bucketName} in region {awsRegion} of account number:{subscriberAccountId} not encrypted due to following error: \n {error}')
            message = f'S3 Bucket {bucketName} in region {awsRegion}of account number: {subscriberAccountId} not encrypted due to following error: \n {error}'
            logger.debug(f'sent error email')
            notify_email(message, recipient=violatorEmail, cc=adminEmail)
            return True


def enable_encryption(bucketName, s3, subscriberAccountId, awsRegion,adminEmail,violatorEmail):
    """ This function enables the encryption on bucket """
    try:
        s3.put_bucket_encryption(Bucket=bucketName, ServerSideEncryptionConfiguration={'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]})
        logger.debug(f'Encrypted successfully and sending mail')
        message = f'{bucketName} in region: {awsRegion} in account number: {subscriberAccountId} successfully encrypted.'
        if notify_email(message, recipient=violatorEmail, cc=adminEmail):
            logger.debug(f'Message sent successfully')
        return True
    except botocore.exceptions.ClientError as error:
        message = f'Bucket {bucketName} in region:{awsRegion} of account number:{subscriberAccountId} is not encrypted successfully due to following \n {error}'
        logger.error(f'Bucket {bucketName} in region:{awsRegion}of account number: \
                     {subscriberAccountId} is not encrypted successfully due to following \n {error}')
        notify_email(message, recipient=violatorEmail, cc=adminEmail)

def lambda_handler(event, context):
    """This is main lambda function"""
    logger.debug(event)
    adminEmail = None
    bucketName = event['detail']['requestParameters']['bucketName']
    subscriberAccountId = event['account']
    arn = event['detail']['userIdentity']['arn']
    sessionName = context.function_name
    awsRegion = event['detail']['awsRegion']
    s3 = get_aws_client('s3', subscriberAccountId, awsRegion, ROLE_NAME, sessionName)
    adminEmail = get_account_admin_email(subscriberAccountId)
    if adminEmail is not None:
        adminEmail = [adminEmail]
    logger.info(f'Got Admin email address {adminEmail}')
    email = arn.split('/')[-1]
    if re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email) is not None:
      violatorEmail = [email]
    else:
      violatorEmail = adminEmail
      adminEmail = None
    logger.info(f'Viloator email is {violatorEmail}')
    if not encryption_enabled(bucketName, s3, subscriberAccountId, awsRegion,adminEmail,violatorEmail):
        encryption_status = enable_encryption(bucketName, s3, subscriberAccountId, awsRegion,adminEmail,violatorEmail)
        if encryption_status:
            logger.debug(f'Lambda {sessionName} executed and {bucketName} in {subscriberAccountId} successfully encrypted')
        else:
            logger.error(f'Lambda Execution Failed.')
