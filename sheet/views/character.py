import re
from typing import Any, Tuple  # noqa

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import CharacterEquipForm, LevelUpForm, Roll20Form, SkillPointsForm
from ..models import equipment, items
from ..models.abilities import inverse_abilities
from ..models.character import Character, UnlockedAbility
from ..models.level_up import LevelUp
from ..roll20 import api, login


def owns_character_or_superuser(request: HttpRequest, character: Character) -> bool:
    if request.user.is_superuser or character.user.username == request.user.username:
        return True
    else:
        messages.error(request, 'User not authorized to edit this character.')
        return False


@login_required
def stats(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)
    return render(request, 'stats.html', context={'character': character,
                                                  'Rarity': equipment.Rarity})


@login_required
def cls(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)
    return render(request, 'class.html', context={'character': character})


@login_required
def party(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)
    return render(request, 'party.html', context={'character': character})


@login_required
def unlock_abilities(request: HttpRequest, character_id: int) -> HttpResponse:
    # messages.error(request, 'Hello world error.')
    character = get_object_or_404(Character, pk=character_id)

    if request.method == 'POST' and owns_character_or_superuser(request, character):
        for parameter, value in request.POST.items():
            match = re.match(r'^(?P<action_type>lock|unlock)\s(?P<ability_index>[0-9]+)$', value)
            if match is not None:
                ability_index = int(match.group('ability_index'))
                ability = character.cls.abilities[ability_index]

                action_type = match.group('action_type')
                if action_type == 'lock':
                    for unlocked_ability in character.unlockedability_set.all():
                        if unlocked_ability.ability is ability:
                            # Do not allow the player to re-lock an ability if it is a
                            # prerequisite for another ability they have already unlocked.
                            lock_ability = True
                            for owned_ability in character.unlocked_abilities:
                                if ability in owned_ability.prerequisites:
                                    messages.error(request,
                                                   'Cannot lock ability {} because it is a '
                                                   'prerequisite for {}.'.format(
                                                       ability.name,
                                                       owned_ability.name))
                                    lock_ability = False
                            if lock_ability:
                                unlocked_ability.delete()
                elif action_type == 'unlock':
                    if character.available_ap > 0:
                        unlock_ability = True
                        for prerequisite in ability.prerequisites:
                            if prerequisite not in character.unlocked_abilities:
                                messages.error(request,
                                               'Prerequisite {} not met for ability {}.'.format(
                                                   prerequisite.name, ability.name))
                                unlock_ability = False

                        if unlock_ability:
                            new_unlocked_ability = UnlockedAbility(
                                character=character,
                                ability_enum=inverse_abilities[ability])
                            new_unlocked_ability.save()
                    else:
                        messages.error(request, 'Not enough available AP.')

        return redirect(reverse(unlock_abilities, args=[character_id]))

    return render(request, 'abilities.html', context={'character': character})


@login_required
def combos(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)
    return render(request, 'combos.html', context={'character': character})


@login_required
def equip(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)

    if request.method == 'POST' and owns_character_or_superuser(request, character):
        equip_form = CharacterEquipForm(request.POST)
        if equip_form.is_valid():
            character.utility_enum = equip_form.cleaned_data['utility_enum']
            character.head_enum = equip_form.cleaned_data['head_enum']
            character.neck_enum = equip_form.cleaned_data['neck_enum']
            character.chest_enum = equip_form.cleaned_data['chest_enum']
            character.shield_enum = equip_form.cleaned_data['shield_enum']
            character.right_hand_enum = equip_form.cleaned_data['right_hand_enum']
            character.left_hand_enum = equip_form.cleaned_data['left_hand_enum']
            character.feet_enum = equip_form.cleaned_data['feet_enum']
            character.weapon_enum = equip_form.cleaned_data['weapon_enum']

            # Validate character meets requirements for equipment.
            if (character.get_attribute(character.utility.min_attribute) <
                    character.utility.min_attribute_value):
                equip_form.add_error('utility_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.utility.name,
                                         character.utility.min_attribute_value,
                                         character.utility.min_attribute.name.upper()))
            elif (character.get_attribute(character.head.min_attribute) <
                  character.head.min_attribute_value):
                equip_form.add_error('head_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.head.name,
                                         character.head.min_attribute_value,
                                         character.head.min_attribute.name.upper()))
            elif (character.get_attribute(character.neck.min_attribute) <
                  character.neck.min_attribute_value):
                equip_form.add_error('neck_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.neck.name,
                                         character.neck.min_attribute_value,
                                         character.neck.min_attribute.name.upper()))
            elif (character.get_attribute(character.chest.min_attribute) <
                  character.chest.min_attribute_value):
                equip_form.add_error('chest_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.chest.name,
                                         character.chest.min_attribute_value,
                                         character.chest.min_attribute.name.upper()))
            elif (character.get_attribute(character.shield.min_attribute) <
                  character.shield.min_attribute_value):
                equip_form.add_error('shield_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.shield.name,
                                         character.shield.min_attribute_value,
                                         character.shield.min_attribute.name.upper()))
            elif (character.get_attribute(character.right_hand.min_attribute) <
                  character.right_hand.min_attribute_value):
                equip_form.add_error('right_hand_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.right_hand.name,
                                         character.right_hand.min_attribute_value,
                                         character.right_hand.min_attribute.name.upper()))
            elif (character.get_attribute(character.left_hand.min_attribute) <
                  character.left_hand.min_attribute_value):
                equip_form.add_error('left_hand_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.left_hand.name,
                                         character.left_hand.min_attribute_value,
                                         character.left_hand.min_attribute.name.upper()))
            elif (character.get_attribute(character.feet.min_attribute) <
                  character.feet.min_attribute_value):
                equip_form.add_error('feet_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.feet.name,
                                         character.feet.min_attribute_value,
                                         character.feet.min_attribute.name.upper()))
            elif (character.get_attribute(character.weapon.min_attribute) <
                  character.weapon.min_attribute_value):
                equip_form.add_error('weapon_enum',
                                     error='Requirements not met for {}.  Need {}{}.'.format(
                                         character.weapon.name,
                                         character.weapon.min_attribute_value,
                                         character.weapon.min_attribute.name.upper()))
            elif (character.weapon.is_two_handed and
                    character.shield_enum is not items.Shields.empty):
                equip_form.add_error('shield_enum',
                                     error='Cannot equip a shield and a two-handed weapon.')
            elif ((character.right_hand.is_two_handed and
                    character.left_hand_enum is not items.Hands.empty) or
                    (character.left_hand.is_two_handed and
                     character.right_hand_enum is not items.Hands.empty)):
                equip_form.add_error('right_hand_enum',
                                     error='Cannot equip two-handed Hand item and an item in '
                                           'other hand.')
            elif not character.can_use_weapon:
                equip_form.add_error('weapon_enum',
                                     error='Class {cls} cannot use {style} {type} weapons'.format(
                                        cls=character.cls.name, style=character.weapon.style.name,
                                        type=character.weapon.type.name))
            else:
                character.save()
                return redirect(reverse(stats, args=[character_id]))
    else:
        equip_form = CharacterEquipForm(
            initial={
                'utility_enum': character.utility_enum,
                'head_enum': character.head_enum,
                'neck_enum': character.neck_enum,
                'chest_enum': character.chest_enum,
                'shield_enum': character.shield_enum,
                'right_hand_enum': character.right_hand_enum,
                'left_hand_enum': character.left_hand_enum,
                'feet_enum': character.feet_enum,
                'weapon_enum': character.weapon_enum
            })

    return render(request, 'equip.html',
                  context={'equip_form': equip_form,
                           'character': character})


@login_required
def level_up(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)

    if request.method == 'POST' and owns_character_or_superuser(request, character):
        level_up_form = LevelUpForm(request.POST)

        # Check if a delete input button was pressed to remove an old LevelUp.
        for parameter, value in request.POST.items():
            match = re.match(r'^delete\s(?P<levelup_id>[0-9]+)$', value)
            if match is not None:
                LevelUp.objects.get(pk=match.group('levelup_id')).delete()
                level_up_form = LevelUpForm()

        # Otherwise, user is creating a new LevelUp.
        if level_up_form.is_valid():
            hd_roll = level_up_form.cleaned_data['hd_roll']
            md_roll = level_up_form.cleaned_data['md_roll']
            sd_roll = level_up_form.cleaned_data['sd_roll']
            if hd_roll > character.cls.hd:
                level_up_form.add_error('hd_roll',
                                        error='HD roll higher than HD: {hd_roll}>{hd}'.format(
                                            hd_roll=hd_roll, hd=character.cls.hd))
            elif md_roll > character.cls.md:
                level_up_form.add_error('md_roll',
                                        error='MD roll higher than MD: {md_roll}>{md}'.format(
                                            md_roll=md_roll, md=character.cls.md))
            elif sd_roll > character.cls.sd:
                level_up_form.add_error('sd_roll',
                                        error='SD roll higher than SD: {sd_roll}>{sd}'.format(
                                            sd_roll=sd_roll, sd=character.cls.sd))
            elif (character.lvl == 0 and
                  (hd_roll != character.cls.hd or
                   md_roll != character.cls.md or
                   sd_roll != character.cls.sd)):
                level_up_form.add_error('hd_roll',
                                        error='For LVL 1: HD, MD, and SD are assigned maximum '
                                              'roll values.')
            else:
                new_level_up = level_up_form.save(commit=False)
                new_level_up.character = character
                new_level_up.save()
                level_up_form = LevelUpForm()
    else:
        if character.lvl == 0:
            level_up_form = LevelUpForm(
                initial={'hd_roll': character.cls.hd,
                         'md_roll': character.cls.md,
                         'sd_roll': character.cls.sd})
        else:
            level_up_form = LevelUpForm()

    return render(request, 'level_up.html',
                  context={'level_up_form': level_up_form,
                           'character': character})


@login_required
def skill_points(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)

    if request.method == 'POST' and owns_character_or_superuser(request, character):
        skill_points_form = SkillPointsForm(request.POST)
        if skill_points_form.is_valid():
            assigned_ath = skill_points_form.cleaned_data['assigned_ath']
            assigned_ste = skill_points_form.cleaned_data['assigned_ste']
            assigned_for = skill_points_form.cleaned_data['assigned_for']
            assigned_apt = skill_points_form.cleaned_data['assigned_apt']
            assigned_per = skill_points_form.cleaned_data['assigned_per']
            assigned_spe = skill_points_form.cleaned_data['assigned_spe']
            if (assigned_ath + assigned_ste + assigned_for + assigned_apt + assigned_per +
                    assigned_spe > character.sp):
                skill_points_form.add_error('assigned_ath',
                                            error='Too many SP assigned. Max: {sp}'.format(
                                                sp=character.sp))
            elif assigned_ath > character.max_sp_per_skill:
                skill_points_form.add_error('assigned_ath',
                                            error='Assigned ATH too high. Max: {max_sp}'.format(
                                                max_sp=character.max_sp_per_skill))
            elif assigned_ste > character.max_sp_per_skill:
                skill_points_form.add_error('assigned_ste',
                                            error='Assigned STE too high. Max: {max_sp}'.format(
                                                max_sp=character.max_sp_per_skill))
            elif assigned_for > character.max_sp_per_skill:
                skill_points_form.add_error('assigned_for',
                                            error='Assigned FOR too high. Max: {max_sp}'.format(
                                                max_sp=character.max_sp_per_skill))
            elif assigned_apt > character.max_sp_per_skill:
                skill_points_form.add_error('assigned_apt',
                                            error='Assigned APT too high. Max: {max_sp}'.format(
                                                max_sp=character.max_sp_per_skill))
            elif assigned_per > character.max_sp_per_skill:
                skill_points_form.add_error('assigned_per',
                                            error='Assigned PER too high. Max: {max_sp}'.format(
                                                max_sp=character.max_sp_per_skill))
            elif assigned_spe > character.max_sp_per_skill:
                skill_points_form.add_error('assigned_spe',
                                            error='Assigned SPE too high. Max: {max_sp}'.format(
                                                max_sp=character.max_sp_per_skill))
            else:
                character.assigned_ath = assigned_ath
                character.assigned_ste = assigned_ste
                character.assigned_for = assigned_for
                character.assigned_apt = assigned_apt
                character.assigned_per = assigned_per
                character.assigned_spe = assigned_spe
                character.save()
    else:
        skill_points_form = SkillPointsForm(
            initial={'assigned_ath': character.assigned_ath,
                     'assigned_ste': character.assigned_ste,
                     'assigned_for': character.assigned_for,
                     'assigned_apt': character.assigned_apt,
                     'assigned_per': character.assigned_per,
                     'assigned_spe': character.assigned_spe}
        )

    return render(request, 'skill_points.html',
                  context={'skill_points_form': skill_points_form,
                           'character': character})


@login_required
def roll20(request: HttpRequest, character_id: int) -> HttpResponse:
    character = get_object_or_404(Character, pk=character_id)

    campaign_name = ''
    if request.method == 'POST' and owns_character_or_superuser(request, character):
        roll20_form = Roll20Form(request.POST)
        if roll20_form.is_valid():
            password = roll20_form.cleaned_data['password']
            sync_abilities = roll20_form.cleaned_data['sync_abilities']
            sync_attributes = roll20_form.cleaned_data['sync_attributes']
            sync_combos = roll20_form.cleaned_data['sync_combos']
            sync_weapons = roll20_form.cleaned_data['sync_weapons']

            roll20_login = login.login(email=request.user.email, password=password,
                                       campaign_id=character.party.roll20_campaign_id)
            campaign_name = roll20_login.campaign_name

            character_id = api.get_character_id(login=roll20_login, character_name=character.name)
            attributes_to_sync = {
                'LVL': character.lvl,
                'HP': character.hp,
                'MP': character.mp,
                'SPEED': character.speed,
                'PDEF': character.pdef,
                'MDEF': character.mdef,
                'PRED': character.pred,
                'MRED': character.mred,
                'REG': character.reg,
                'RD': character.rd,
                'VIS': character.vis,
                'BPAC': character.bpac,
                'BMAC': character.bmac,
                'ATH': character.ath,
                'STE': character.ste,
                'FOR': character.fort,
                'APT': character.apt,
                'PER': character.per,
                'SPE': character.spe,
                'STR': character.stren,
                'DEX': character.dex,
                'CON': character.con,
                'INT': character.intel,
                'WIS': character.wis,
                'CHA': character.cha,
                'HD': 'd' + str(character.cls.hd),
                'MD': 'd' + str(character.cls.md),
                'SD': 'd' + str(character.cls.sd),

                'SlashingVUL': int(character.vul_set.vul.slashing),
                'PiercingVUL': int(character.vul_set.vul.piercing),
                'BludgeoningVUL': int(character.vul_set.vul.bludgeoning),
                'FireVUL': int(character.vul_set.vul.fire),
                'ColdVUL': int(character.vul_set.vul.cold),
                'LightningVUL': int(character.vul_set.vul.lightning),
                'AcidVUL': int(character.vul_set.vul.acid),
                'PoisonVUL': int(character.vul_set.vul.poison),
                'ForceVUL': int(character.vul_set.vul.force),
                'PsychicVUL': int(character.vul_set.vul.psychic),

                'SlashingRES': int(character.vul_set.res.slashing),
                'PiercingRES': int(character.vul_set.res.piercing),
                'BludgeoningRES': int(character.vul_set.res.bludgeoning),
                'FireRES': int(character.vul_set.res.fire),
                'ColdRES': int(character.vul_set.res.cold),
                'LightningRES': int(character.vul_set.res.lightning),
                'AcidRES': int(character.vul_set.res.acid),
                'PoisonRES': int(character.vul_set.res.poison),
                'ForceRES': int(character.vul_set.res.force),
                'PsychicRES': int(character.vul_set.res.psychic),

                'SlashingIMU': int(character.vul_set.imu.slashing),
                'PiercingIMU': int(character.vul_set.imu.piercing),
                'BludgeoningIMU': int(character.vul_set.imu.bludgeoning),
                'FireIMU': int(character.vul_set.imu.fire),
                'ColdIMU': int(character.vul_set.imu.cold),
                'LightningIMU': int(character.vul_set.imu.lightning),
                'AcidIMU': int(character.vul_set.imu.acid),
                'PoisonIMU': int(character.vul_set.imu.poison),
                'ForceIMU': int(character.vul_set.imu.force),
                'PsychicIMU': int(character.vul_set.imu.psychic),
            }
            if sync_attributes:
                for attribute_name, attribute_value in attributes_to_sync.items():
                    api.set_attribute(login=roll20_login, character_id=character_id,
                                      attribute_name=attribute_name,
                                      attribute_value=attribute_value,
                                      attribute_position=api.AttributePosition.current)
                    api.set_attribute(login=roll20_login, character_id=character_id,
                                      attribute_name=attribute_name,
                                      attribute_value=attribute_value,
                                      attribute_position=api.AttributePosition.max)

            # TODO: Abilities and Weapons could derive from the same base class Macroable.
            abilities_to_sync = ()  # type: Tuple[Any, ...]
            if sync_abilities:
                abilities_to_sync += character.unlocked_abilities
            if sync_combos:
                abilities_to_sync += character.unlocked_combos
            if sync_weapons:
                abilities_to_sync += (character.weapon,)
            for ability in abilities_to_sync:
                if not api.ability_exists(login=roll20_login, character_id=character_id,
                                          ability_name=ability.name):
                    api.create_ability(login=roll20_login, character_id=character_id,
                                       ability_name=ability.name,
                                       ability_action=ability.macro)
                else:
                    api.update_ability(login=roll20_login, character_id=character_id,
                                       ability_name=ability.name,
                                       ability_action=ability.macro)

    else:
        roll20_form = Roll20Form()

    return render(request, 'roll20.html',
                  context={'roll20_form': roll20_form,
                           'character': character,
                           'user': request.user,
                           'campaign_name': campaign_name})
