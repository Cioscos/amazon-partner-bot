import logging
import os
from typing import Union, Optional, Dict

logger = logging.getLogger(__name__)

KEYRING: Dict[str, Optional[str]] = {
    'Telegram': None,
    'Partner': None
}


def keyring_initialize() -> Union[bool, None]:
    """
    Initialize the keyring.
    This functions load from decrypted partition the keys needed.

    :return: True if everything went fine, False otherwise.
    """
    root_path = os.environ.get('ENV')
    if root_path is None:
        logger.error('Root directory is not set')
        return None

    # Get the telegram token key
    with open(os.path.join(root_path, 'telegram.dat')) as file:
        KEYRING['Telegram'] = file.read().strip()
        logger.info("Telegram token read")

    # Get the telegram token key
    with open(os.path.join(root_path, 'partner.dat')) as file:
        KEYRING['Partner'] = file.read().strip()
        logger.info("Partner tag read")

    return True


def keyring_get(service: str) -> Union[str, None]:
    """
    Get the key related to a service from the keyring.

    :param service: The service which get the key.
    :return: The keyring in the keyring. None if it's not present.
    """
    if service not in KEYRING:
        logger.warning('Key of service %s not found in keyring' % service)
        return None

    return KEYRING[service]
