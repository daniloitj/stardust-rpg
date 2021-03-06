"""URLS:
    /jukeboxplaylist/
    /players/
    /pages/
    /macros/player/-JoQ7XOdNq1qd1qz-jjs/
    /paths/page/-JoQ8N4X4kuBVHB7bHYP/
    /texts/page/-Jot0iSLWfpewBY_ZfFD/
    /graphics/page/-JjXbDyhiQ5BIfsKUIAF/
    /characters/
    /handouts/
    /decks/
    /rollabletables/
    /hands/
    /custfxs/
    /char-attribs/char/-JnxHiSp18UmTHuHLG54/
    /char-abils/char/-JnxHiSp18UmTHuHLG54/
    /decks/-JjksiRpAGV6DM1ZdjVY/cards/
    /cardtrades/
"""

import enum
import json
import logging
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import requests

from .login import Roll20Login

logger = logging.getLogger(__name__)


class Roll20CharacterNotFoundError(RuntimeError):
    pass


class Roll20PermissionError(RuntimeError):
    pass


def get_character_id(login: Roll20Login, character_name: str) -> str:
    """
    Notes:
        Used for debugging:
            characters = json.loads(requests.get(url).text)
            json.dumps(characters, indent=4) for debugging.
    """
    url = f'{login.firebase_root}{login.campaign_path}/characters.json?auth={login.auth_token}'
    characters = json.loads(requests.get(url).text)
    characters_data = {c['name']: c['id'] for c in characters.values()}
    logger.debug(f'Found characters: {characters_data.keys()}')
    try:
        character_id = characters_data[character_name]
        logger.debug(f'Found character: {character_name} {character_id}')
        return character_id
    except KeyError as ex:
        raise Roll20CharacterNotFoundError(
            f'Character "{character_name}" does not exist in this campaign.') from ex


@enum.unique
class AttributePosition(enum.Enum):
    current = 'current'
    max = 'max'


def get_attributes_ids(login: Roll20Login, character_id: str) -> Dict[str, str]:
    url = (f'{login.firebase_root}{login.campaign_path}/'
           f'char-attribs/char/{character_id}.json?auth={login.auth_token}')
    attributes = json.loads(requests.get(url).text)
    attribute_ids = {c['name']: c['id'] for c in attributes.values()}
    logger.debug(f'Found attributes: {attribute_ids.keys()}')
    return attribute_ids


def set_attributes(login: Roll20Login, character_id: str,
                   attributes: Mapping[str, Union[str, int]],
                   attribute_position: AttributePosition = AttributePosition.current) -> None:
    attribute_ids = get_attributes_ids(login=login, character_id=character_id)

    for attribute_name, attribute_value in attributes.items():
        # Cast int values to str.
        attribute_value = str(attribute_value)

        attribute_id = attribute_ids[attribute_name]
        url = (f'{login.firebase_root}{login.campaign_path}/char-attribs/char/{character_id}/'
               f'{attribute_id}/.json?auth={login.auth_token}')
        response = requests.patch(url,
                                  data=json.dumps({attribute_position.value: attribute_value}))
        if response.status_code == requests.status_codes.codes.UNAUTHORIZED:
            raise Roll20PermissionError('Permission denied trying to set attribute.')
        else:
            updated_attribute = json.loads(response.text)[attribute_position.value]
            logger.debug(f'New {attribute_name}: {updated_attribute}')


def get_player_id(login: Roll20Login, d20_user_id: int) -> str:
    url = f'{login.firebase_root}{login.campaign_path}/players/.json?auth={login.auth_token}'
    players = json.loads(requests.get(url).text)
    correct_player_id = None
    for player_id, player_info in players.items():
        if player_info['d20userid'] == str(d20_user_id):
            correct_player_id = player_id

    correct_player_info = players[correct_player_id]
    logger.debug(correct_player_info)
    return correct_player_id


def get_macros(login: Roll20Login, player_id: str) -> Optional[Tuple[str, ...]]:
    url = f'{login.firebase_root}{login.campaign_path}/macros/.json?auth={login.auth_token}'
    all_players_macros = json.loads(requests.get(url).text)
    logger.debug(json.dumps(all_players_macros, indent=4))
    try:
        player_macros = all_players_macros['player'][player_id]
        logger.debug(json.dumps(player_macros, indent=4))
        return player_macros
    except KeyError:
        logger.debug(f'No macros found for Player ID: {player_id}')
        return None


def update_ability(login: Roll20Login, character_id: str, ability_id: str,
                   ability_action: str) -> None:
    url = (f'{login.firebase_root}{login.campaign_path}/char-abils/char/'
           f'{character_id}/{ability_id}/.json?auth={login.auth_token}')
    response = requests.patch(url, data=json.dumps({'action': ability_action}))
    if response.status_code == requests.status_codes.codes.UNAUTHORIZED:
        raise Roll20PermissionError('Permission denied trying to update ability.')
    else:
        updated_action = json.loads(response.text)['action']
        logger.debug(f'{ability_id} updated action: {updated_action}')


def create_ability(login: Roll20Login, character_id: str, ability_name: str, ability_action: str,
                   is_token_action: bool = True) -> None:
    new_ability = {'action': ability_action,
                   'name': ability_name,
                   'istokenaction': is_token_action}
    url = (f'{login.firebase_root}{login.campaign_path}/'
           f'char-abils/char/{character_id}.json?auth={login.auth_token}')
    response = requests.post(url, data=json.dumps(new_ability))
    if response.status_code == requests.status_codes.codes.UNAUTHORIZED:
        raise Roll20PermissionError('Permission denied trying to create ability.')
    else:
        new_ability_id = json.loads(response.text)['name']
        logger.debug(f'Created {ability_name} {new_ability_id}')

        url = (f'{login.firebase_root}{login.campaign_path}/char-abils/char/'
               f'{character_id}/{new_ability_id}/.json?auth={login.auth_token}')
        requests.patch(url, data=json.dumps({'id': new_ability_id}))


def get_ability_ids(login: Roll20Login, character_id: str) -> Dict[str, str]:
    url = (f'{login.firebase_root}{login.campaign_path}/'
           f'char-abils/char.json?auth={login.auth_token}')
    all_character_abilities = json.loads(requests.get(url).text)
    ability_ids = {c['name']: c['id'] for c in all_character_abilities[character_id].values()}
    logger.debug(f'Found attributes: {ability_ids.keys()}')
    return ability_ids


def set_abilities(login: Roll20Login, character_id: str, abilities: Tuple[Any, ...]) -> None:
    ability_ids = get_ability_ids(login=login, character_id=character_id)

    for ability in abilities:
        # See if ability already exists to decide whether to update or create it.
        if ability.name in ability_ids.keys():
            logger.debug(f'Updating {ability.name}')
            update_ability(login=login,
                           character_id=character_id,
                           ability_id=ability_ids[ability.name],
                           ability_action=ability.macro)
        else:
            logger.debug(f'Creating {ability.name}')
            create_ability(login=login, character_id=character_id, ability_name=ability.name,
                           ability_action=ability.macro)
