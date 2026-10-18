"""The Meego game plugin: registers the Meego adapter and its hooks with the core app.

The core app only calls optional hooks on registered adapters; everything
Meego-specific lives here. Heavy modules are imported lazily inside hooks so
the plugin can be loaded while the core is still importing.
"""
from __future__ import annotations
from ..util import RevivalError, atomic_json, now, read_json
from . import timer_mod, lifecycle_mod
from .adapter import MeegoAdapter, ORIGINAL_SHA


class MeegoPlugin(MeegoAdapter):
    title = 'The Meego'
    recommended_path = 'local_backend'
    recommendation_reason = 'Reviewed Meego local responder preserves the native game, with provisional simulation and limited features.'
    binary_targets = frozenset({'lib/armeabi/libverde.so', 'AndroidManifest.xml', 'resources.arsc'})
    operation_types = frozenset({'meego_timer_panel', 'meego_lifecycle_panel'})
    verify_note = 'Meego requires a guided Android gameplay test. Signing and host service tests do not certify the game.'
    controls = 'Controls: touch or trackpad.'
    save_file = 'saves/village.json'
    mods = True

    # Analysis
    def detect(self, p, z, finding, endpoints):
        if p['apk_sha256'] != ORIGINAL_SHA:
            return False
        finding('meego_adapter', 'Exact reviewed The Meego v1.32 APK; experimental local responder available', ['APK SHA256', 'assets/TechTree.plist', 'assets/Info.plist', 'lib/armeabi/libverde.so'], 'high', 'discovered')
        import plistlib
        info = plistlib.loads(z.read('assets/Info.plist'))
        for key in ['ServerURL', 'SecureServerURL', 'MediaURL']:
            endpoints.append({'url': str(info.get(key, '')), 'evidence': 'assets/Info.plist:' + key, 'classification': 'discovered configured endpoint; server behavior unproven'})
        finding('meego_scope', 'Earlier Deck gameplay was reported; this launcher, new package/signature and reverse transport still require Android verification', ['docs/MEEGO.md'], 'medium', 'inferred')
        return True

    # Restoration operations beyond the core text/byte patches
    def validate_operation(self, op, p):
        if op.get('type') == 'meego_lifecycle_panel':
            if (p.get('adapter') != self.name or p['apk_sha256'] != ORIGINAL_SHA
                    or op.get('file') not in lifecycle_mod.ASSETS
                    or op.get('expected_sha256') != lifecycle_mod.ASSETS[op['file']]
                    or op.get('revision') != lifecycle_mod.REVISION):
                raise RevivalError('Villager age panel requires the exact reviewed original asset.')
            return
        if (p.get('adapter') != self.name or p['apk_sha256'] != ORIGINAL_SHA or op['file'] != timer_mod.ASSET or
                op.get('expected_sha256') != timer_mod.ASSET_SHA or op.get('revision') != timer_mod.REVISION):
            raise RevivalError('Timer panel operation requires the exact reviewed Meego asset.')

    def apply_operation(self, op, raw):
        if op.get('type') == 'meego_lifecycle_panel':
            return lifecycle_mod.patched_panel(op['file'],raw), 'Native stats age-20 control and stat-preserving revival confirmation.\n'
        return timer_mod.patched_panel(raw), 'Reviewed Meego countdown panel: move bound completion button beside X and add Skip timer label.\n'

    # Saves and local service
    def validate_save(self, state):
        from .savefile import validate_meego_save
        validate_meego_save(state)

    def config_path(self, store, p):
        from .backend import config_path
        return config_path(store, p)

    def start_backend(self, data, config, port, apk=None, profile=None):
        from .backend import MeegoBackend
        native = bool(profile) and profile.get('restoration', {}).get('plan', {}).get('meego_client_fixes', {}).get('native_timer_mod') == 1
        return MeegoBackend(data, config, port, apk=apk, native_timer_mod=native).start()

    # Launcher integration
    def prepared_current(self, previous, p):
        from . import camera
        return camera.prepared(previous, p['runtime'].get('meego_timer_hz', 60))

    def before_play(self, service, p, runtime, ctx):
        """Upgrade stale Meego clients once, selecting timing from this guest.

        Called only by normal Play after runtime readiness. Preparation uses
        the existing signing identity and immutable original; Android install
        still uses -r. No save import/reset or gameplay verification occurs.
        """
        from . import camera, frame_pacing
        from ..launcher.tools_setup import health
        from ..restoration import Restorer
        ctx.step('Reading the active game display')
        try:
            hz = frame_pacing.active_timer_hz(runtime.shell('dumpsys', 'display', timeout=5))
        except RevivalError:
            hz = 60
        if camera.prepared(p.get('restoration', {}), hz):
            return p
        if not health()['preparation_ready']:
            raise RevivalError('Meego needs its villager controls update, but preparation tools are missing. Open Setup and select Install preparation tools. The previous APK and saves are preserved.')
        ctx.step('Preparing Meego client controls (' + str(hz) + ' Hz)')
        p['runtime']['meego_timer_hz'] = hz
        service.store.save(p)
        # Restorer keeps the previous working artifact if preparation fails;
        # successful preparation records the revision/rate in the signed plan.
        p = Restorer(service.store).prepare(p['id'], p['restoration']['path'], progress=ctx.step)
        p.setdefault('launcher', {})['prepared_at'] = now()
        service.store.save(p)
        return p

    def mods_dialog(self, service, game, parent):
        from .mods_dialog import ModsDialog
        return ModsDialog(service, game, parent)

    def guided_test_dialog(self, window):
        from .guided_dialog import MeegoTestDialog
        return MeegoTestDialog(window)

    def game_actions(self, p):
        return [{'key': 'new_village', 'icon': 'refresh', 'title': 'New village',
                 'description': 'Starts with two Meego and no bonus supplies. Your previous island is backed up.',
                 'button': 'New village (no bonuses)'}]

    def run_action(self, service, game, key, ctx):
        if key != 'new_village':
            raise RevivalError('Unknown Meego action.')
        from ..saves import Saves
        from .backend import config_path
        from .engine.server import initial_village
        from .savefile import validate_meego_save
        p = service.store.load(game)
        if p.get('adapter') != self.name or p['restoration']['path'] != 'local_backend':
            raise RevivalError('Prepare Meego before creating a village.')
        if service.active and service.active['game'] != game:
            raise RevivalError('Stop the other running game first.')
        config = config_path(service.store, p)
        seed = read_json(config / 'starter-packet.json')
        fresh = initial_village(seed, rules=read_json(config / 'local-rules.json'))
        validate_meego_save(fresh)
        service.stop(ctx)
        save = service.store.directory(game) / 'saves/village.json'
        backup = None
        if save.exists():
            ctx.step('Backing up the previous village')
            backup = Saves(service.store).backup(game)
        ctx.step('Creating a fresh village without bonus supplies or skulls')
        atomic_json(save, fresh)
        return {'created': True, 'previous_backup': backup, 'starting_villagers': len(fresh['game_state']['all_villagers']),
                'original_defaults_verified': False}


def register(add):
    add(MeegoPlugin())
