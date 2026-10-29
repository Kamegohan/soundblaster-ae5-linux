"""Welche Regler die App zeigt, wie sie heißen und wohin sie gehören.

PROFILE_CONTROLS landen in Klangprofilen (Effekte, EQ, Mikrofon-Effekte).
DEVICE_CONTROLS sind Geräteeinstellungen (gelten für jedes Profil).
Lautstärken stehen absichtlich in keiner der beiden Listen: Ein Profilwechsel
soll nie lauter machen.
"""

from .i18n import GERMAN, tr

EQ_BANDS = [f"EQ Band{i} Playback Volume" for i in range(10)]
EQ_FREQUENCIES = ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
EQ_CENTER = 24  # Rohwert für 0 dB; 0..48 entspricht -24..+24 dB in 1-dB-Schritten (Treiber)


def eq_db(raw: int) -> int:
    return raw - EQ_CENTER


def eq_raw(db: float) -> int:
    return max(0, min(48, EQ_CENTER + round(db)))


# Werte der Equalizer-Voreinstellungen aus dem Treiber (ca0132_alt_eq_presets, in dB).
# Der Treiber setzt sie nur im DSP und bewegt die Band-Regler nicht – die App setzt
# deshalb die Bänder selbst (auf ganze dB gerundet).
EQ_PRESET_DB = {
    "Flat":      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Acoustic":  [0, 1.1, 2.0, 0, 0, 0, 0, 2.0, 2.0, 2.0],
    "Classical": [0, 6.0, 6.0, 3.1, 0, 0, 0, 0, 3.1, 3.1],
    "Country":   [-1.2, 0, 1.3, 1.3, 1.1, 0, 0, 2.0, 3.1, 4.0],
    "Dance":     [-1.2, 2.0, 3.1, 4.2, -1.2, -1.2, 0, 0, 4.0, 4.0],
    "Jazz":      [0, 0, 1.1, 4.0, 4.0, 4.0, 0, 1.1, 3.1, 3.1],
    "New Age":   [0, 2.0, 2.0, 0, 0, 0, 1.1, 2.0, 2.0, 2.0],
    "Pop":       [-1.6, 0, 2.0, 2.0, 0, -1.2, -1.2, 0, 3.1, 6.0],
    "Rock":      [-1.2, -1.2, 1.1, 2.0, -1.2, -1.2, 0, 0, 4.0, 4.0],
    "Vocal":     [-2.0, -1.2, -1.2, 0, 3.1, 4.0, 3.1, 0, 0, 1.1],
}

EQ_PRESET_LABELS = {"Flat": "Linear", "Acoustic": "Akustik", "Classical": "Klassik",
                    "Dance": "Dance", "New Age": "New Age", "Vocal": "Gesang"}


# (Schalter, Stärke-Regler, Anzeigename, Beschreibung)
EFFECTS = [
    ("FX: Surround Playback Switch", "FX: Surround Playback Volume", "Surround",
     tr("Virtueller Raumklang für Kopfhörer und Stereo-Lautsprecher",
        "Virtual surround for headphones and stereo speakers")),
    ("FX: Crystalizer Playback Switch", "FX: Crystalizer Playback Volume", "Crystalizer",
     tr("Stellt Höhen und Details komprimierter Musik wieder her",
        "Restores highs and detail lost in compressed music")),
    ("FX: X-Bass Playback Switch", "FX: X-Bass Playback Volume", "Bass (X-Bass)",
     tr("Verstärkt tiefe Frequenzen", "Boosts low frequencies")),
    ("FX: Smart Volume Playback Switch", "FX: Smart Volume Playback Volume", "Smart Volume",
     tr("Gleicht Lautstärkesprünge aus", "Evens out sudden volume changes")),
    ("FX: Dialog Plus Playback Switch", "FX: Dialog Plus Playback Volume", "Dialog Plus",
     tr("Macht Sprache in Filmen und Spielen verständlicher",
        "Makes speech in movies and games easier to understand")),
]

OUTFX_SWITCH = "Enable OutFX Playback Switch"
EQ_SWITCH = "FX: Equalizer Playback Switch"
EQ_PRESET = "FX: Equalizer Preset Switch"
XBASS_CROSSOVER = "FX: X-Bass Crossover Playback Volume"
SMART_VOLUME_MODE = "FX: Smart Volume Setting"

MIC_SWITCHES = [
    ("Enable InFX Capture Switch", tr("Mikrofon-Effekte aktiv", "Microphone effects enabled")),
    ("FX: Voice Focus Capture Switch", "Voice Focus"),
    ("FX: Noise Reduction Capture Switch", tr("Rauschunterdrückung", "Noise reduction")),
    ("FX: Mic SVM Capture Switch", tr("Pegelausgleich (Mic SVM)", "Level control (Mic SVM)")),
]
MIC_SVM_LEVEL = "SVM Level Capture Volume"
VOICE_FX = "VoiceFX Capture Switch"
INPUT_SOURCE = "Input Source"
MIC_BOOST = "Mic Boost Capture Switch"

HEADPHONE_GAIN = "AE-5: Headphone Gain"
SOUND_FILTER = "AE-5: Sound Filter"
SURROUND_CONFIG = "Surround Channel Config"

PROFILE_CONTROLS = (
    [OUTFX_SWITCH, EQ_SWITCH, EQ_PRESET, XBASS_CROSSOVER, SMART_VOLUME_MODE]
    + [c for e in EFFECTS for c in e[:2]]
    + EQ_BANDS
    + [c for c, _ in MIC_SWITCHES]
    + [MIC_SVM_LEVEL, VOICE_FX]
)

DEVICE_CONTROLS = [HEADPHONE_GAIN, SOUND_FILTER, SURROUND_CONFIG, INPUT_SOURCE, MIC_BOOST]

# Deutsche Anzeigenamen für Auswahllisten
ITEM_LABELS = {
    "Low (16-31  Ohms)": "Niedrig (16–31 Ω)",
    "Medium (32-149  Ohms)": "Mittel (32–149 Ω)",
    "High (150-600  Ohms)": "Hoch (150–600 Ω)",
    "Slow Roll Off": "Langsamer Abfall",
    "Minimum Phase": "Minimale Phase",
    "Fast Roll Off": "Schneller Abfall",
    "Microphone": "Mikrofon",
    "Line In": "Line-Eingang",
    "Front Microphone": "Mikrofon vorne",
    "Night": "Nacht",
    "Loud": "Laut",
    **EQ_PRESET_LABELS,
}


def label(item: str) -> str:
    """Anzeigename eines Listeneintrags (der Treiber liefert englische Namen)."""
    if not GERMAN:
        return item.replace("  ", " ").replace("Ohms", "Ω")
    return ITEM_LABELS.get(item, item)


# --- Tooltips (Deutsch) ------------------------------------------------------------------
# Erklärungen zum Überfahren mit der Maus. Schlüssel = ALSA-Reglername.
_TOOLTIPS_DE = {
    OUTFX_SWITCH: "Hauptschalter für alle Klangeffekte (Surround, Crystalizer, Bass, "
                  "Smart Volume, Dialog Plus, Equalizer). Aus = unbearbeiteter Klang.",
    "FX: Surround Playback Switch": "Erzeugt einen virtuellen Raumklang: Ton wirkt, als käme er von "
                                    "außerhalb des Kopfes. Gut für Spiele und Filme, für Musik oft unnötig.",
    "FX: Surround Playback Volume": "Stärke des Raumklangs. Höhere Werte wirken weiter, können aber "
                                    "Stimmen etwas hohler klingen lassen.",
    "FX: Crystalizer Playback Switch": "Stellt Höhen und Dynamik wieder her, die bei komprimierter Musik "
                                       "(MP3, Streaming) verloren gehen.",
    "FX: Crystalizer Playback Volume": "Stärke des Crystalizers. Zu hoch kann scharf oder zischelnd klingen.",
    "FX: X-Bass Playback Switch": "Verstärkt tiefe Frequenzen für mehr Druck im Bass.",
    "FX: X-Bass Playback Volume": "Stärke der Bassanhebung.",
    XBASS_CROSSOVER: "Bis zu welcher Frequenz X-Bass wirkt (10–1000 Hz). Niedrig = nur Tiefbass, "
                     "höher = auch Grundton. 80 Hz ist ein guter Startwert.",
    "FX: Smart Volume Playback Switch": "Gleicht Lautstärkesprünge aus: leise Stellen lauter, laute leiser. "
                                        "Praktisch bei Filmen oder wechselnden Quellen.",
    "FX: Smart Volume Playback Volume": "Wie stark Smart Volume eingreift.",
    SMART_VOLUME_MODE: "Normal = ausgewogen. Laut = hebt insgesamt stärker an. "
                       "Nacht = starke Begrenzung, damit Explosionen nicht laut werden.",
    "FX: Dialog Plus Playback Switch": "Hebt Sprache hervor, damit Dialoge in Filmen und Spielen "
                                       "besser verständlich sind.",
    "FX: Dialog Plus Playback Volume": "Wie stark Sprache hervorgehoben wird.",
    EQ_SWITCH: "Schaltet den 10-Band-Equalizer ein oder aus. Aus = alle Bänder wirkungslos.",
    EQ_PRESET: "Fertige Klangkurven. Beim Auswählen setzt die App die zehn Bänder auf die Werte "
               "der Voreinstellung; danach kannst du sie frei anpassen.",
    HEADPHONE_GAIN: "Verstärkung des Kopfhörerausgangs. Richtet sich nach der Impedanz (Ω) des "
                    "Kopfhörers: hochohmige Modelle brauchen mehr Spannung. "
                    "Zu niedrig = zu leise, zu hoch bei niederohmigen Kopfhörern = Rauschen und Gefahr für Gehör.",
    SOUND_FILTER: "Rekonstruktionsfilter des DAC (Digital-Analog-Wandler). Er glättet das Signal zwischen "
                  "den digitalen Abtastwerten. Die Varianten unterscheiden sich nur oberhalb von ~18 kHz "
                  "und im Zeitverhalten – der Unterschied ist sehr klein.",
    SURROUND_CONFIG: "Wie viele Lautsprecher am Line-Out hängen (2.0 = Stereo, 5.1 = Heimkino). "
                     "Für Kopfhörer ohne Bedeutung.",
    INPUT_SOURCE: "Welcher Eingang der AE-5 aufgenommen wird.",
    MIC_BOOST: "Vorverstärkung für ein Mikrofon an der AE-5. Nur erhöhen, wenn es zu leise ist – "
               "mehr Verstärkung bringt auch mehr Rauschen.",
    "Enable InFX Capture Switch": "Hauptschalter für die Mikrofon-Effekte darunter.",
    "FX: Voice Focus Capture Switch": "Konzentriert die Aufnahme auf deine Stimme und dämpft Geräusche "
                                      "von der Seite.",
    "FX: Noise Reduction Capture Switch": "Filtert gleichmäßiges Hintergrundrauschen (Lüfter, Brummen) heraus.",
    "FX: Mic SVM Capture Switch": "Gleicht die Mikrofonlautstärke automatisch an (leise lauter, laut leiser).",
    MIC_SVM_LEVEL: "Wie stark der Pegelausgleich des Mikrofons eingreift.",
    VOICE_FX: "Verändert deine Stimme (z. B. Ork, Elf). Neutral = keine Veränderung.",
}

# Erklärungen zu einzelnen Einträgen von Auswahllisten
_ITEM_TOOLTIPS_DE = {
    "Low (16-31  Ohms)": "Für niederohmige Kopfhörer und In-Ears (16–31 Ω).",
    "Medium (32-149  Ohms)": "Für die meisten Kopfhörer (32–149 Ω), z. B. DT 770 Pro 80 Ω.",
    "High (150-600  Ohms)": "Für hochohmige Studio-Kopfhörer (150–600 Ω), z. B. DT 770 Pro 250 Ω.",
    "Slow Roll Off": "Sanfter Abfall: kaum Nachschwingen, Höhen fallen ganz oben (ab ~18 kHz) leicht ab. "
                     "Gilt als „weicher, natürlicher“.",
    "Minimum Phase": "Kein Vorschwingen vor Impulsen (nur danach). Wirkt bei Schlagzeug oft "
                     "„knackiger“; leichte Phasenverschiebung in den Höhen.",
    "Fast Roll Off": "Steiler Abfall: Höhen bleiben bis 20 kHz linear, dafür etwas mehr Vor- und "
                     "Nachschwingen. Messtechnisch der „neutralste“ Filter.",
    "Normal": "Ausgewogener Ausgleich.",
    "Loud": "Hebt leise Stellen stärker an.",
    "Night": "Begrenzt laute Stellen stark – gut, wenn andere schlafen.",
}


# --- Tooltips (English) --------------------------------------------------------
_TOOLTIPS_EN = {
    OUTFX_SWITCH: "Master switch for all sound effects (Surround, Crystalizer, Bass, Smart Volume, "
                  "Dialog Plus, Equalizer). Off = unprocessed sound.",
    "FX: Surround Playback Switch": "Creates virtual surround: sound seems to come from outside your head. "
                                    "Good for games and movies, often unnecessary for music.",
    "FX: Surround Playback Volume": "Strength of the surround effect. Higher values feel wider but can make "
                                    "voices sound slightly hollow.",
    "FX: Crystalizer Playback Switch": "Restores highs and dynamics lost in compressed music (MP3, streaming).",
    "FX: Crystalizer Playback Volume": "Strength of the Crystalizer. Too high can sound harsh or sibilant.",
    "FX: X-Bass Playback Switch": "Boosts low frequencies for more punch.",
    "FX: X-Bass Playback Volume": "Amount of bass boost.",
    XBASS_CROSSOVER: "Up to which frequency X-Bass works (10–1000 Hz). Low = sub-bass only, higher = also "
                     "the fundamental range. 80 Hz is a good starting point.",
    "FX: Smart Volume Playback Switch": "Evens out volume jumps: quiet parts louder, loud parts quieter. "
                                        "Useful for movies or mixed sources.",
    "FX: Smart Volume Playback Volume": "How strongly Smart Volume intervenes.",
    SMART_VOLUME_MODE: "Normal = balanced. Loud = boosts more overall. Night = strong limiting so "
                       "explosions don't get loud.",
    "FX: Dialog Plus Playback Switch": "Emphasizes speech so dialogue in movies and games is easier to follow.",
    "FX: Dialog Plus Playback Volume": "How strongly speech is emphasized.",
    EQ_SWITCH: "Turns the 10-band equalizer on or off. Off = all bands have no effect.",
    EQ_PRESET: "Ready-made curves. When selected, the app sets the ten bands to the preset's values; "
               "you can adjust them freely afterwards.",
    HEADPHONE_GAIN: "Gain of the headphone output. Depends on the impedance (Ω) of your headphones: "
                    "high-impedance models need more voltage. Too low = too quiet, too high with "
                    "low-impedance headphones = noise and a risk to your hearing.",
    SOUND_FILTER: "Reconstruction filter of the DAC (digital-to-analog converter). It smooths the signal "
                  "between digital samples. The variants only differ above ~18 kHz and in their timing "
                  "behaviour – the difference is very small.",
    SURROUND_CONFIG: "How many speakers are connected to the line out (2.0 = stereo, 5.1 = home theater). "
                     "Irrelevant for headphones.",
    INPUT_SOURCE: "Which input of the AE-5 is recorded.",
    MIC_BOOST: "Pre-amplification for a microphone connected to the AE-5. Only raise it if it is too quiet – "
               "more gain also means more noise.",
    "Enable InFX Capture Switch": "Master switch for the microphone effects below.",
    "FX: Voice Focus Capture Switch": "Focuses the recording on your voice and dampens sound from the sides.",
    "FX: Noise Reduction Capture Switch": "Filters out steady background noise (fans, hum).",
    "FX: Mic SVM Capture Switch": "Automatically evens out the microphone level (quiet louder, loud quieter).",
    MIC_SVM_LEVEL: "How strongly the microphone level control intervenes.",
    VOICE_FX: "Changes your voice (e.g. Orc, Elf). Neutral = no change.",
}

_ITEM_TOOLTIPS_EN = {
    "Low (16-31  Ohms)": "For low-impedance headphones and in-ears (16–31 Ω).",
    "Medium (32-149  Ohms)": "For most headphones (32–149 Ω), e.g. DT 770 Pro 80 Ω.",
    "High (150-600  Ohms)": "For high-impedance studio headphones (150–600 Ω), e.g. DT 770 Pro 250 Ω.",
    "Slow Roll Off": "Gentle roll-off: hardly any ringing, the very top end (above ~18 kHz) drops slightly. "
                     "Often described as “softer, more natural”.",
    "Minimum Phase": "No pre-ringing before impulses (only after). Drums often feel “snappier”; slight phase "
                     "shift in the treble.",
    "Fast Roll Off": "Steep roll-off: treble stays flat up to 20 kHz, with a bit more pre- and post-ringing. "
                     "Technically the most “neutral” filter.",
    "Normal": "Balanced leveling.",
    "Loud": "Boosts quiet parts more.",
    "Night": "Strongly limits loud parts – good when others are asleep.",
}

TOOLTIPS = _TOOLTIPS_DE if GERMAN else _TOOLTIPS_EN
ITEM_TOOLTIPS = _ITEM_TOOLTIPS_DE if GERMAN else _ITEM_TOOLTIPS_EN
