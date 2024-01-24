# Porting to api 8 made easier by baport.(https://github.com/bombsquad-community/baport)
# Released under the MIT License. See LICENSE for details.
#
"""Elimination mini-game."""

# Maded by Froshlee14
# Update by SEBASTIAN2059

# ba_meta require api 8
# (see https://ballistica.net/wiki/meta-tag-system)

from __future__ import annotations

from typing import TYPE_CHECKING

import babase
import bauiv1 as bui
import bascenev1 as bs
import _babase
import random
from bascenev1lib.actor.spazfactory import SpazFactory
from bascenev1lib.actor.scoreboard import Scoreboard
from bascenev1lib.actor import spazbot as stdbot
from bascenev1lib.gameutils import SharedObjects as so

if TYPE_CHECKING:
    from typing import (Any, Tuple, Dict, Type, List, Sequence, Optional,
                        Union)


class Icon(bs.Actor):
    """Creates in in-game icon on screen."""

    def __init__(self,
                 player: Player,
                 position: Tuple[float, float],
                 scale: float,
                 show_lives: bool = True,
                 show_death: bool = True,
                 name_scale: float = 1.0,
                 name_maxwidth: float = 115.0,
                 flatness: float = 1.0,
                 shadow: float = 1.0):
        super().__init__()

        self._player = player
        self._show_lives = show_lives
        self._show_death = show_death
        self._name_scale = name_scale
        self._outline_tex = bs.gettexture('characterIconMask')

        icon = player.get_icon()
        self.node = bs.newnode('image',
                               delegate=self,
                               attrs={
                                   'texture': icon['texture'],
                                   'tint_texture': icon['tint_texture'],
                                   'tint_color': icon['tint_color'],
                                   'vr_depth': 400,
                                   'tint2_color': icon['tint2_color'],
                                   'mask_texture': self._outline_tex,
                                   'opacity': 1.0,
                                   'absolute_scale': True,
                                   'attach': 'bottomCenter'
                               })
        self._name_text = bs.newnode(
            'text',
            owner=self.node,
            attrs={
                'text': babase.Lstr(value=player.getname()),
                'color': babase.safecolor(player.team.color),
                'h_align': 'center',
                'v_align': 'center',
                'vr_depth': 410,
                'maxwidth': name_maxwidth,
                'shadow': shadow,
                'flatness': flatness,
                'h_attach': 'center',
                'v_attach': 'bottom'
            })
        if self._show_lives:
            self._lives_text = bs.newnode('text',
                                          owner=self.node,
                                          attrs={
                                              'text': 'x0',
                                              'color': (1, 1, 0.5),
                                              'h_align': 'left',
                                              'vr_depth': 430,
                                              'shadow': 1.0,
                                              'flatness': 1.0,
                                              'h_attach': 'center',
                                              'v_attach': 'bottom'
                                          })
        self.set_position_and_scale(position, scale)

    def set_position_and_scale(self, position: Tuple[float, float],
                               scale: float) -> None:
        """(Re)position the icon."""
        assert self.node
        self.node.position = position
        self.node.scale = [70.0 * scale]
        self._name_text.position = (position[0], position[1] + scale * 52.0)
        self._name_text.scale = 1.0 * scale * self._name_scale
        if self._show_lives:
            self._lives_text.position = (position[0] + scale * 10.0,
                                         position[1] - scale * 43.0)
            self._lives_text.scale = 1.0 * scale

    def update_for_lives(self) -> None:
        """Update for the target player's current lives."""
        if self._player:
            lives = self._player.lives
        else:
            lives = 0
        if self._show_lives:
            if lives > 0:
                self._lives_text.text = 'x' + str(lives - 1)
            else:
                self._lives_text.text = ''
        if lives == 0:
            self._name_text.opacity = 0.2
            assert self.node
            self.node.color = (0.7, 0.3, 0.3)
            self.node.opacity = 0.2

    def handle_player_spawned(self) -> None:
        """Our player spawned; hooray!"""
        if not self.node:
            return
        self.node.opacity = 1.0
        self.update_for_lives()

    def handle_player_died(self) -> None:
        """Well poo; our player died."""
        if not self.node:
            return
        if self._show_death:
            bs.animate(
                self.node, 'opacity', {
                    0.00: 1.0,
                    0.05: 0.0,
                    0.10: 1.0,
                    0.15: 0.0,
                    0.20: 1.0,
                    0.25: 0.0,
                    0.30: 1.0,
                    0.35: 0.0,
                    0.40: 1.0,
                    0.45: 0.0,
                    0.50: 1.0,
                    0.55: 0.2
                })
            lives = self._player.lives
            if lives == 0:
                bs.timer(0.6, self.update_for_lives)

    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            self.node.delete()
            return None
        return super().handlemessage(msg)


class Player(bs.Player['Team']):
    """Our player type for this game."""

    def __init__(self) -> None:
        self.lives = 0
        self.icons: List[Icon] = []


class Team(bs.Team[Player]):
    """Our team type for this game."""

    def __init__(self) -> None:
        self.survival_seconds: Optional[int] = None
        self.spawn_order: List[Player] = []


lang = bs.app.lang.language
if lang == 'Spanish':
    description = 'Mantente en la zona segura.'
    join_description = 'Corre hacia la zona segura.'
    kill_timer = 'Kill timer: '
else:
    description = 'Stay in the safe zone.'
    join_description = 'Run into the safe zone'
    kill_timer = 'Kill timer: '

# ba_meta export bascenev1.GameActivity


class SafeZoneGame(bs.TeamGameActivity[Player, Team]):
    """Game type where last player(s) left alive win."""

    name = 'Safe Zone'
    description = description
    scoreconfig = bs.ScoreConfig(label='Survived',
                                 scoretype=bs.ScoreType.SECONDS,
                                 none_is_winner=True)
    # Show messages when players die since it's meaningful here.
    announce_player_deaths = True

    @classmethod
    def get_available_settings(
            cls, sessiontype: Type[bs.Session]) -> List[babase.Setting]:
        settings = [
            bs.IntSetting(
                'Lives Per Player',
                default=2,
                min_value=1,
                max_value=10,
                increment=1,
            ),
            bs.IntChoiceSetting(
                'Time Limit',
                choices=[
                    ('None', 0),
                    ('1 Minute', 60),
                    ('2 Minutes', 120),
                    ('5 Minutes', 300),
                    ('10 Minutes', 600),
                    ('20 Minutes', 1200),
                ],
                default=0,
            ),
            bs.FloatChoiceSetting(
                'Respawn Times',
                choices=[
                    ('Short', 0.25),
                    ('Normal', 0.5),
                ],
                default=0.5,
            ),
            bs.BoolSetting('Epic Mode', default=False),
        ]
        if issubclass(sessiontype, bs.DualTeamSession):
            settings.append(bs.BoolSetting('Solo Mode', default=False))
            settings.append(
                bs.BoolSetting('Balance Total Lives', default=False))
        return settings

    @classmethod
    def supports_session_type(cls, sessiontype: Type[bs.Session]) -> bool:
        return (issubclass(sessiontype, bs.DualTeamSession)
                or issubclass(sessiontype, bs.FreeForAllSession))

    @classmethod
    def get_supported_maps(cls, sessiontype: Type[bs.Session]) -> List[str]:
        return ['Football Stadium', 'Hockey Stadium']

    def __init__(self, settings: dict):
        super().__init__(settings)
        self._scoreboard = Scoreboard()
        self._start_time: Optional[float] = None
        self._vs_text: Optional[bs.Actor] = None
        self._round_end_timer: Optional[bs.Timer] = None
        self._epic_mode = bool(settings['Epic Mode'])
        self._lives_per_player = int(settings['Lives Per Player'])
        self._time_limit = float(settings['Time Limit'])
        self._balance_total_lives = bool(
            settings.get('Balance Total Lives', False))
        self._solo_mode = bool(settings.get('Solo Mode', False))

        # Base class overrides:
        self.slow_motion = self._epic_mode
        self.default_music = (bs.MusicType.EPIC
                              if self._epic_mode else bs.MusicType.SURVIVAL)

        self._tick_sound = bs.getsound('tick')

    def get_instance_description(self) -> Union[str, Sequence]:
        return join_description

    def get_instance_description_short(self) -> Union[str, Sequence]:
        return 'last team standing wins' if isinstance(
            self.session, bs.DualTeamSession) else 'last one standing wins'

    def on_player_join(self, player: Player) -> None:

        # No longer allowing mid-game joiners here; too easy to exploit.
        if self.has_begun():

            # Make sure their team has survival seconds set if they're all dead
            # (otherwise blocked new ffa players are considered 'still alive'
            # in score tallying).
            if (self._get_total_team_lives(player.team) == 0
                    and player.team.survival_seconds is None):
                player.team.survival_seconds = 0
            bs.broadcastmessage(
                babase.Lstr(resource='playerDelayedJoinText',
                            subs=[('${PLAYER}', player.getname(full=True))]),
                color=(0, 1, 0),
            )
            return

        player.lives = self._lives_per_player

        if self._solo_mode:
            player.team.spawn_order.append(player)
            self._update_solo_mode()
        else:
            # Create our icon and spawn.
            player.icons = [Icon(player, position=(0, 50), scale=0.8)]
            if player.lives > 0:
                self.spawn_player(player)

        # Don't waste time doing this until begin.
        if self.has_begun():
            self._update_icons()

    def on_begin(self) -> None:
        super().on_begin()
        self._start_time = bs.time()
        self.setup_standard_time_limit(self._time_limit)
        # self.setup_standard_powerup_drops()

        bs.timer(5, self.spawn_zone)
        self._bots = stdbot.SpazBotSet()
        bs.timer(3, babase.Call(self.add_bot, 'left'))
        bs.timer(3, babase.Call(self.add_bot, 'right'))
        if len(self.initialplayerinfos) > 4:
            bs.timer(5, babase.Call(self.add_bot, 'right'))
            bs.timer(5, babase.Call(self.add_bot, 'left'))

        if self._solo_mode:
            self._vs_text = bs.NodeActor(
                bs.newnode('text',
                           attrs={
                               'position': (0, 105),
                               'h_attach': 'center',
                               'h_align': 'center',
                               'maxwidth': 200,
                               'shadow': 0.5,
                               'vr_depth': 390,
                               'scale': 0.6,
                               'v_attach': 'bottom',
                               'color': (0.8, 0.8, 0.3, 1.0),
                               'text': babase.Lstr(resource='vsText')
                           }))

        # If balance-team-lives is on, add lives to the smaller team until
        # total lives match.
        if (isinstance(self.session, bs.DualTeamSession)
                and self._balance_total_lives and self.teams[0].players
                and self.teams[1].players):
            if self._get_total_team_lives(
                    self.teams[0]) < self._get_total_team_lives(self.teams[1]):
                lesser_team = self.teams[0]
                greater_team = self.teams[1]
            else:
                lesser_team = self.teams[1]
                greater_team = self.teams[0]
            add_index = 0
            while (self._get_total_team_lives(lesser_team) <
                   self._get_total_team_lives(greater_team)):
                lesser_team.players[add_index].lives += 1
                add_index = (add_index + 1) % len(lesser_team.players)

        self._update_icons()

        # We could check game-over conditions at explicit trigger points,
        # but lets just do the simple thing and poll it.
        bs.timer(1.0, self._update, repeat=True)

    def spawn_zone(self):
        self.zone_pos = (random.randrange(-10, 10), 0.05, random.randrange(-5, 5))
        self.zone = bs.newnode('locator', attrs={'shape': 'circle', 'position': self.zone_pos, 'color': (
            1, 1, 0), 'opacity': 0.8, 'draw_beauty': True, 'additive': False, 'drawShadow': False})
        self.zone_limit = bs.newnode('locator', attrs={'shape': 'circleOutline', 'position': self.zone_pos, 'color': (
            1, 0.2, 0.2), 'opacity': 0.8, 'draw_beauty': True, 'additive': False, 'drawShadow': False})
        bs.animate_array(self.zone, 'size', 1, {0: [0], 0.3: [
                         self.get_players_count()*0.85], 0.35: [self.get_players_count()*0.8]})
        bs.animate_array(self.zone_limit, 'size', 1, {0: [0], 0.3: [
                         self.get_players_count()*1.2], 0.35: [self.get_players_count()*0.95]})
        self.last_players_count = self.get_players_count()
        bs.getsound('laserReverse').play()
        self.start_timer()
        self.move_zone()

    def delete_zone(self):
        self.zone.delete()
        self.zone = None
        self.zone_limit.delete()
        self.zone_limit = None
        bs.getsound('shieldDown').play()
        bs.timer(1, self.spawn_zone)

    def move_zone(self):
        if self.zone_pos[0] > 0:
            x = random.randrange(0, 10)
        else:
            x = random.randrange(-10, 0)

        if self.zone_pos[2] > 0:
            y = random.randrange(0, 5)
        else:
            y = random.randrange(-5, 0)

        new_pos = (x, 0.05, y)
        bs.animate_array(self.zone, 'position', 3, {0: self.zone.position, 8: new_pos})
        bs.animate_array(self.zone_limit, 'position', 3, {0: self.zone_limit.position, 8: new_pos})

    def start_timer(self):
        count = self.get_players_count()
        self._time_remaining = 10 if count > 9 else count-1 if count > 6 else count if count > 2 else count*2
        self._timer_x = bs.Timer(1.0, bs.WeakCall(self.tick), repeat=True)
        # gnode = bs.getactivity().globalsnode
        # tint = gnode.tint
        # bs.animate_array(gnode,'tint',3,{0:tint,self._time_remaining*1.5:(1.0,0.5,0.5),self._time_remaining*1.55:tint})

    def stop_timer(self):
        self._time = None
        self._timer_x = None

    def tick(self):
        self.check_players()
        self._time = bs.NodeActor(bs.newnode('text',
                                             attrs={'v_attach': 'top', 'h_attach': 'center',
                                                    'text': kill_timer+str(self._time_remaining)+'s',
                                                    'opacity': 0.8, 'maxwidth': 100, 'h_align': 'center',
                                                    'v_align': 'center', 'shadow': 1.0, 'flatness': 1.0,
                                                    'color': (1, 1, 1), 'scale': 1.5, 'position': (0, -50)}
                                             )
                                  )
        self._time_remaining -= 1
        self._tick_sound.play()

    def check_players(self):
        if self._time_remaining <= 0:
            self.stop_timer()
            bs.animate_array(self.zone, 'size', 1, {
                             0: [self.last_players_count*0.8], 1.4: [self.last_players_count*0.8], 1.5: [0]})
            bs.animate_array(self.zone_limit, 'size', 1, {
                             0: [self.last_players_count*0.95], 1.45: [self.last_players_count*0.95], 1.5: [0]})
            bs.timer(1.5, self.delete_zone)
            for player in self.players:
                if not player.actor is None:
                    if player.actor.is_alive():
                        p1 = player.actor.node.position
                        p2 = self.zone.position
                        diff = (babase.Vec3(p1[0]-p2[0], 0.0, p1[2]-p2[2]))
                        dist = (diff.length())
                        if dist > (self.get_players_count()*0.7):
                            player.actor.handlemessage(bs.DieMessage())

    def get_players_count(self):
        count = 0
        for player in self.players:
            if not player.actor is None:
                if player.actor.is_alive():
                    count += 1
        return count

    def _update_solo_mode(self) -> None:
        # For both teams, find the first player on the spawn order list with
        # lives remaining and spawn them if they're not alive.
        for team in self.teams:
            # Prune dead players from the spawn order.
            team.spawn_order = [p for p in team.spawn_order if p]
            for player in team.spawn_order:
                assert isinstance(player, Player)
                if player.lives > 0:
                    if not player.is_alive():
                        self.spawn_player(player)
                    break

    def _update_icons(self) -> None:
        # pylint: disable=too-many-branches

        # In free-for-all mode, everyone is just lined up along the bottom.
        if isinstance(self.session, bs.FreeForAllSession):
            count = len(self.teams)
            x_offs = 85
            xval = x_offs * (count - 1) * -0.5
            for team in self.teams:
                if len(team.players) == 1:
                    player = team.players[0]
                    for icon in player.icons:
                        icon.set_position_and_scale((xval, 30), 0.7)
                        icon.update_for_lives()
                    xval += x_offs

        # In teams mode we split up teams.
        else:
            if self._solo_mode:
                # First off, clear out all icons.
                for player in self.players:
                    player.icons = []

                # Now for each team, cycle through our available players
                # adding icons.
                for team in self.teams:
                    if team.id == 0:
                        xval = -60
                        x_offs = -78
                    else:
                        xval = 60
                        x_offs = 78
                    is_first = True
                    test_lives = 1
                    while True:
                        players_with_lives = [
                            p for p in team.spawn_order
                            if p and p.lives >= test_lives
                        ]
                        if not players_with_lives:
                            break
                        for player in players_with_lives:
                            player.icons.append(
                                Icon(player,
                                     position=(xval, (40 if is_first else 25)),
                                     scale=1.0 if is_first else 0.5,
                                     name_maxwidth=130 if is_first else 75,
                                     name_scale=0.8 if is_first else 1.0,
                                     flatness=0.0 if is_first else 1.0,
                                     shadow=0.5 if is_first else 1.0,
                                     show_death=is_first,
                                     show_lives=False))
                            xval += x_offs * (0.8 if is_first else 0.56)
                            is_first = False
                        test_lives += 1
            # Non-solo mode.
            else:
                for team in self.teams:
                    if team.id == 0:
                        xval = -50
                        x_offs = -85
                    else:
                        xval = 50
                        x_offs = 85
                    for player in team.players:
                        for icon in player.icons:
                            icon.set_position_and_scale((xval, 30), 0.7)
                            icon.update_for_lives()
                        xval += x_offs

    def _get_spawn_point(self, player: Player) -> Optional[babase.Vec3]:
        del player  # Unused.

        # In solo-mode, if there's an existing live player on the map, spawn at
        # whichever spot is farthest from them (keeps the action spread out).
        if self._solo_mode:
            living_player = None
            living_player_pos = None
            for team in self.teams:
                for tplayer in team.players:
                    if tplayer.is_alive():
                        assert tplayer.node
                        ppos = tplayer.node.position
                        living_player = tplayer
                        living_player_pos = ppos
                        break
            if living_player:
                assert living_player_pos is not None
                player_pos = babase.Vec3(living_player_pos)
                points: List[Tuple[float, babase.Vec3]] = []
                for team in self.teams:
                    start_pos = babase.Vec3(self.map.get_start_position(team.id))
                    points.append(
                        ((start_pos - player_pos).length(), start_pos))
                # Hmm.. we need to sorting vectors too?
                points.sort(key=lambda x: x[0])
                return points[-1][1]
        return None

    def spawn_player(self, player: Player) -> bs.Actor:
        actor = self.spawn_player_spaz(player, self._get_spawn_point(player))
        if not self._solo_mode:
            bs.timer(0.3, babase.Call(self._print_lives, player))

        # spaz but *without* the ability to attack or pick stuff up.
        actor.connect_controls_to_player(enable_punch=False,
                                         enable_bomb=False,
                                         enable_pickup=False)

        # If we have any icons, update their state.
        for icon in player.icons:
            icon.handle_player_spawned()
        return actor

    def _print_lives(self, player: Player) -> None:
        from bascenev1lib.actor import popuptext

        # We get called in a timer so it's possible our player has left/etc.
        if not player or not player.is_alive() or not player.node:
            return

        popuptext.PopupText('x' + str(player.lives - 1),
                            color=(1, 1, 0, 1),
                            offset=(0, -0.8, 0),
                            random_offset=0.0,
                            scale=1.8,
                            position=player.node.position).autoretain()

    def on_player_leave(self, player: Player) -> None:
        super().on_player_leave(player)
        player.icons = []

        # Remove us from spawn-order.
        if self._solo_mode:
            if player in player.team.spawn_order:
                player.team.spawn_order.remove(player)

        # Update icons in a moment since our team will be gone from the
        # list then.
        bs.timer(0, self._update_icons)

        # If the player to leave was the last in spawn order and had
        # their final turn currently in-progress, mark the survival time
        # for their team.
        if self._get_total_team_lives(player.team) == 0:
            assert self._start_time is not None
            player.team.survival_seconds = int(bs.time() - self._start_time)

    def _get_total_team_lives(self, team: Team) -> int:
        return sum(player.lives for player in team.players)

    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.PlayerDiedMessage):

            # Augment standard behavior.
            super().handlemessage(msg)
            player: Player = msg.getplayer(Player)

            player.lives -= 1
            if player.lives < 0:
                babase.print_error(
                    "Got lives < 0 in Elim; this shouldn't happen. solo:" +
                    str(self._solo_mode))
                player.lives = 0

            # If we have any icons, update their state.
            for icon in player.icons:
                icon.handle_player_died()

            # Play big death sound on our last death
            # or for every one in solo mode.
            if self._solo_mode or player.lives == 0:
                SpazFactory.get().single_player_death_sound.play()

            # If we hit zero lives, we're dead (and our team might be too).
            if player.lives == 0:
                # If the whole team is now dead, mark their survival time.
                if self._get_total_team_lives(player.team) == 0:
                    assert self._start_time is not None
                    player.team.survival_seconds = int(bs.time() -
                                                       self._start_time)
            else:
                # Otherwise, in regular mode, respawn.
                if not self._solo_mode:
                    self.respawn_player(player)

            # In solo, put ourself at the back of the spawn order.
            if self._solo_mode:
                player.team.spawn_order.remove(player)
                player.team.spawn_order.append(player)
        elif isinstance(msg, stdbot.SpazBotDiedMessage):
            self._on_spaz_bot_died(msg)

    def _on_spaz_bot_died(self, die_msg):
        bs.timer(1, babase.Call(self.add_bot, die_msg.spazbot.node.position))

    def _on_bot_spawn(self, spaz):
        spaz.update_callback = self.move_bot
        spaz_type = type(spaz)
        spaz._charge_speed = self._get_bot_speed(spaz_type)

    def add_bot(self, pos=None):
        if pos == 'left':
            position = (-11, 0, random.randrange(-5, 5))
        elif pos == 'right':
            position = (11, 0, random.randrange(-5, 5))
        else:
            position = pos
        self._bots.spawn_bot(self.get_random_bot(), pos=position, spawn_time=1,
                             on_spawn_call=babase.Call(self._on_bot_spawn))

    def move_bot(self, bot):
        p = bot.node.position
        speed = -bot._charge_speed if (p[0] >= -11 and p[0] < 0) else bot._charge_speed

        if (p[0] >= -11) and (p[0] <= 11):
            bot.node.move_left_right = speed
            bot.node.move_up_down = 0.0
            bot.node.run = 0.0
            return True
        return False

    def get_random_bot(self):
        bots = [stdbot.BomberBotStatic, stdbot.TriggerBotStatic]
        return (random.choice(bots))

    def _get_bot_speed(self, bot_type):
        if bot_type == stdbot.BomberBotStatic:
            return 0.48
        elif bot_type == stdbot.TriggerBotStatic:
            return 0.73
        else:
            raise Exception('Invalid bot type to _getBotSpeed(): '+str(bot_type))

    def _update(self) -> None:
        if self._solo_mode:
            # For both teams, find the first player on the spawn order
            # list with lives remaining and spawn them if they're not alive.
            for team in self.teams:
                # Prune dead players from the spawn order.
                team.spawn_order = [p for p in team.spawn_order if p]
                for player in team.spawn_order:
                    assert isinstance(player, Player)
                    if player.lives > 0:
                        if not player.is_alive():
                            self.spawn_player(player)
                            self._update_icons()
                        break

        # If we're down to 1 or fewer living teams, start a timer to end
        # the game (allows the dust to settle and draws to occur if deaths
        # are close enough).
        if len(self._get_living_teams()) < 2:
            self._round_end_timer = bs.Timer(0.5, self.end_game)

    def _get_living_teams(self) -> List[Team]:
        return [
            team for team in self.teams
            if len(team.players) > 0 and any(player.lives > 0
                                             for player in team.players)
        ]

    def end_game(self) -> None:
        if self.has_ended():
            return
        results = bs.GameResults()
        self._vs_text = None  # Kill our 'vs' if its there.
        for team in self.teams:
            results.set_team_score(team, team.survival_seconds)
        self.end(results=results)
