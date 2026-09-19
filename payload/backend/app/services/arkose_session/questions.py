"""YesCaptcha FunCaptchaClassification questions + MatchKey geometry.

Official English `question` strings: CN wiki 2025-08-25 (page 34209793).
Do not send the generic MatchKey chrome sentence. objects[0] is 0-based.
"""

from __future__ import annotations

from dataclasses import dataclass

FALLBACK_COMMENT = (
    "Pick the image that matches the instruction shown on the left. Select exactly one tile."
)
YES_GENERIC_MATCHKEY = (
    "click on the arrows to view different images when the image matches "
    "the example on the left, click submit!"
)

YES_QUESTION_CATALOG: dict[str, str] = {
    "claw_machine": "find the image that has the prize on the left held by the claw in the machine on the right",
    "hopscotchv2": "Use the arrows to move the person to the spot indicated by the cross",
    "hopscotch_v2": "Use the arrows to move the person to the spot indicated by the cross",
    "hopscotch_highsec": "Use the arrows to move the person to the icon indicated by the colored circle",
    "orbit_match_game": "use the arrows to move the icon into the indicated orbit",
    "3d_rollball_animals": "Use the arrows to rotate the animal to face in the direction of the hand",
    "3d_rollball_objects": "Use the arrows to rotate the object to face in the direction of the hand",
    "3d_rollball_objects_v2": "Use the arrows to rotate the object to face in the direction of the hand",
    "3d_rollball_objects_v3": "Use the arrows to rotate the object to face in the direction of the hand",
    "3drollball_v2_var1": "Use the arrows to rotate the object to face in the direction of the hand",
    "3drollball_v2_var2": "Use the arrows to rotate the object to face in the direction of the hand",
    "3d_rollball_objects_multi": "Use the arrows to rotate the animal with the same icon to face where the hand is pointing",
    "3d_rollball_animals_multi": "Use the arrows to rotate the animal with the same icon to face where the hand is pointing",
    "coordinatesmatch": "Using the arrows, move the person to the indicated seat",
    "train_coordinates": "Use the arrows to move the train into the position indicated in the left image",
    "rockstack": "Using the arrows, pick the group of rocks that has the amount indicated on the left",
    "rockstack_v2": "Using the arrows, pick the group of rocks that has the amount indicated on the left",
    "penguins": "Pick the penguin",
    "penguin": "Pick the penguin",
    "penguins_icon": "Pick the penguin",
    "shadows": "Pick the wrong shadow",
    "frankenhead": "Select the animal with the wrong head",
    "card": "Pick the matching cards",
    "unbentobjects": "Pick the object that is not distorted",
    "counting": "Pick the image where the number matches the amount of animals",
    "numericalmatch": "Pick the image where the number matches the amount of animals",
    "dicematch": "Pick the dice pair with the same icon facing up",
    "dice_pair": "Pick the dice pair with the same icon facing up",
    "diceico": "use the arrows to find the image where the number of symbols on the tops of the dice exactly matches the image on the left",
    "icon_segments": "use the arrows to select the image that has the icons in the same order as in the leftmost image",
    "icon_constellation": "select the constellation that most closely resembles the image shown on the left",
    "conveyor_belt_v2": "use the arrows to pick the image where the object directly below the arrow matches the left image",
    "conveyor": "use the arrows to pick the image where the object directly below the arrow matches the left image",
    "darts_matchkey": "use the arrows to choose the image where all the darts add up to the number in the left image",
    "icongrouping": "using the arrows, find the group of icons that the icon on the left would best fit in",
    "icon_connect": "use the arrows to select the image where all the lines are connected to the matching icon",
    "pathfinder": "use the arrows to select the image where the character is pointing to the shortest route, as shown in the leftmost image",
    "cardistance": "use the arrows to find the distance between the two cars that matches the left image",
    "knotscrossescircle": "Select an image of three circles in any direction on a straight line",
    "brokenjigsawbrokenjigsaw_swap": "use the arrows to find the jigsaw puzzle that is missing the puzzle piece shown on the left",
    "watericoncup": "use the arrows to match the symbol on the left with the cup containing the most liquid",
    "bowling": "use the arrows to match the number of pins that fall with the number shown on the left",
    "matchship": "use the arrows to find the image where the red striped pins completely overlap with the boat on the left",
}

YES_WIKI_QUESTIONS = [
    "Pick the bread",
    "Pick one square that shows two identical objects",
    "Pick the penguin",
    "Pick the shadow with a different object silhouette",
    "Pick the dice pair with the same icon facing up",
    "Pick the dice pair whose top sides add up to 14",
    "Pick the matching cards",
    "Pick the animal looking at the shape that matches the shape it's standing on",
    "Pick one square that shows three of the same object.",
    "Pick the mouse that can reach all the cheese in the maze",
    "Pick the mouse that can't reach the cheese",
    "Pick the image where the darts add up to 10",
    "Pick the image that is the correct way up",
    "Pick the dice pair whose top sides add up to 5",
    "Pick the wrong shadow",
    "Select the animal with the wrong head",
    "Pick the shadow that mathes the icons at the top of the image",
    "Pick the spiral galaxy",
    "Pick the image where all animals are walking in the same direction as the arrow",
    "Select the image with the icon order Chair then Fence",
    "Select the image where the total fingers add up to 4",
    "Select the image where the total fingers add up to 3",
    "Pick any square",
    "Select an image of three circles in any direction on a straight line",
    "Pick the image with 3 crosses in a row in any direction",
    "Pick the image where the number matches the amount of animals",
    "Pick the distorted object",
    "Pick the object that is not distorted",
    "Pick the image with only one rope",
    "Pick the image where the darts add up to 8",
    "Pick the image of the brick cube and the striped heart",
    "Pick the image of the brick cube and the striped sphere",
    "Pick the image of the brick heart and the striped heart",
    "Pick the image of the brick sphere and the checkered heart",
    "Pick the image of the checkered cone and the checkered sphere",
    "Pick the image of the fuzzy cone and the brick sphere",
    "Pick the image of the fuzzy cube and the checkered cube",
    "Pick the image of the fuzzy heart and the brick heart",
    "Pick the image of the fuzzy heart and the striped heart",
    "Pick the image of the fuzzy cube and the striped cube",
    "Pick the image of the striped cone and the checkered cube",
    "Pick the image of the brick cone and the striped cone",
    "Pick the image of the striped cube and the checkered cube",
    "Pick the image of the fuzzy sphere and the striped cone",
    "Pick the image of the striped cube and the checkered sphere",
    "Pick the image of the striped cube and the checkered heart",
    "Pick the image of the brick cone and the checkered cube",
    "Pick the image of the striped heart and the checkered cube",
    "Pick the image of the brick cone and the checkered sphere",
    "Pick the image of the fuzzy sphere and the striped cube",
    "Pick the image of 2 striped shapes",
    "Pick the image of 2 checkered shapes",
    "Pick the image with the matching reflection",
    "Pick the image of the person walking up the stairs",
    "Pick the image of the person walking down the stairs",
    "Pick the cube with icons split in half",
    "Pick the puzzle with the wrong pieces",
    "Use the arrows to rotate the animal to face in the direction of the hand",
    "Use the arrows to change the number of objects until it matches the left image",
    "Use the arrows to place the train on the coordinate point shown in the picture on the left",
    "Use the arrows to move the train to the coordinates shown in the picture on the left",
    "Using the arrows, move the person to the indicated seat",
    "Use the arrows to move the person to the spot indicated by the cross",
    "Use the arrows to move the person to the icon indicated by the colored circle",
    "Using the arrows, connect the same two icons with the dotted line as shown on the left",
    "Use the arrows to move the train into the position indicated in the left image",
    "Use the buttons to place the indicated car, in the correct position in the race",
    "Use the arrows to rotate the animal with the same icon to face where the hand is pointing",
    "Use the arrows to rotate the object to face in the direction of the hand",
    "Use the arrows to find the room that matches the left image",
    "Using the arrows, pick the group of rocks that has the amount indicated on the left",
    "using the arrows, find the image where one of the towers of rocks contains the exact amount shown on the left",
    "use the arrows to find the distance between the two cars that matches the left image",
    "use the arrows to choose the image where all the darts add up to the number in the left image",
    "use the arrows to find the image where the number on each ring adds up to the number on the left",
    "use the arrows to move the icon into the indicated orbit",
    "use the arrows to find the jigsaw puzzle that is missing the puzzle piece shown on the left",
    "use the arrows to pick the image where the object directly below the arrow matches the left image",
    "find the image that has the prize on the left held by the claw in the machine on the right",
    "find the image where the rat can reach the exact amount of cheese as the image on the left.",
    "use the arrows to find the basket picture with the same content as shown on the left",
    "use the arrows to match the number of pins that fall with the number shown on the left",
    "use the arrows to choose the image where the winner has the icon shown in the image on the left",
    "use the arrows to select the image where the character is pointing to the shortest route, as shown in the leftmost image",
    "select the constellation that most closely resembles the image shown on the left",
    "use the arrows to select the image that has the icons in the same order as in the leftmost image",
    "use the arrows to select the image where all the lines are connected to the matching icon",
    "use the arrows to find the image where the red striped pins completely overlap with the boat on the left",
    "use the arrows to match the symbol on the left with the cup containing the most liquid",
    "use the arrows to move the characters until they are standing on the same icons as in the picture on the left",
    "use arrows to find the shape whose number of sides equals the number shown on the left",
    "use the arrows to choose the image where the falling balloon has the same icon as shown on the left",
    "use the arrows to move the character across tiles that have the same icons as shown on the left",
    "use the arrows to find the image where the number of symbols on the tops of the dice exactly matches the image on the left",
    "use the arrows to match the icon inside the bubble with the one shown on the left",
    "using the arrows, find the group of icons that the icon on the left would best fit in",
    "Pick the dice pair whose top sides add up to 6",
    "Pick the dice pair whose top sides add up to 7",
    "Pick the dice pair whose top sides add up to 8",
    "Pick the dice pair whose top sides add up to 9",
    "Pick the ant",
    "Pick the apple",
    "Pick the banana",
    "Pick the bat",
    "Pick the bear",
    "Pick the bee",
    "Pick the butterfly",
    "Pick the camel",
    "Pick the cat",
    "Pick the chicken",
    "Pick the cow",
    "Pick the crab",
    "Pick the deer",
    "Pick the dinosaur",
    "Pick the dog",
    "Pick the dolphin",
    "Pick the donut",
    "Pick the duck",
    "Pick the elephant",
    "Pick the frog",
    "Pick the giraffe",
    "Pick the goat",
    "Pick the grapes",
    "Pick the icecream",
    "Pick the ice cream",
    "Pick the kangaroo",
    "Pick the koala",
    "Pick the ladybug",
    "Pick the lion",
    "Pick the lobster",
    "Pick the monkey",
    "Pick the mouse",
    "Pick the octopus",
    "Pick the owl",
    "Pick the parrot",
    "Pick the panda",
    "Pick the pig",
    "Pick the pineapple",
    "Pick the pizza",
    "Pick the rabbit",
    "Pick the rhino",
    "Pick the seal",
    "Pick the shark",
    "Pick the sheep",
    "Pick the snail",
    "Pick the snake",
    "Pick the starfish",
    "Pick the turtle",
    "Pick the zebra",
]

YES_OFFICIAL: set[str] = set()


def _seed_official() -> None:
    for q in YES_WIKI_QUESTIONS:
        if not q:
            continue
        YES_OFFICIAL.add(q)
        k = norm_variant(q)
        if k not in YES_QUESTION_CATALOG:
            YES_QUESTION_CATALOG[k] = q
    for q in YES_QUESTION_CATALOG.values():
        YES_OFFICIAL.add(q)


def norm_variant(s: str) -> str:
    s = (s or "").strip().lower()
    return s.replace("-", "_").replace(" ", "_")


def official_yes_question(s: str) -> str:
    if not s:
        return ""
    return YES_QUESTION_CATALOG.get(norm_variant(s), "")


def yes_question_unusable(q: str) -> bool:
    q = (q or "").strip()
    if not q:
        return True
    if q.casefold() == FALLBACK_COMMENT.casefold():
        return True
    return q.casefold() == YES_GENERIC_MATCHKEY.casefold()


def yes_question_known(question: str) -> bool:
    return not yes_question_unusable(question)


def is_mostly_english(s: str) -> bool:
    if not s:
        return False
    letters = 0
    ascii_n = 0
    for ch in s:
        if ord(ch) <= 127:
            ascii_n += 1
            if ch.isalpha():
                letters += 1
    return ascii_n * 2 >= len(s) and letters > 0


def classification_question(instruction: str, variant: str) -> str:
    human = (instruction or "").strip()
    if " " in human and is_mostly_english(human) and not yes_question_unusable(human):
        return human
    if q := official_yes_question(variant):
        return q
    if q := official_yes_question(instruction):
        return q
    for s in ((variant or "").strip(), (instruction or "").strip()):
        if s and not yes_question_unusable(s):
            return s
    return ""


@dataclass
class VariantSpec:
    comment: str = FALLBACK_COMMENT
    rows: int = 0
    cols: int = 0
    rotate: bool = False


_VARIANT_TABLE: dict[str, VariantSpec] = {
    "claw_machine": VariantSpec("Pick the right-side image that best matches the object on the left.", 1, 6),
    "hopscotchv2": VariantSpec("Pick the panel that matches the example.", 1, 5),
    "hopscotch_highsec": VariantSpec(
        "Use the arrows to move the person to the icon indicated by the colored circle.",
        rotate=True,
    ),
    "icon_segments": VariantSpec("Select the tile that continues the icon sequence.", 1, 6),
    "orbit_match_game": VariantSpec("Pick the matching orbit.", 1, 6),
    "conveyor_belt_v2": VariantSpec("Pick the matching object on the conveyor.", 1, 6),
    "conveyor": VariantSpec("Pick the matching object on the conveyor.", 1, 6),
    "icon_constellation": VariantSpec("Pick the matching icon constellation.", 1, 6),
    "3d_rollball_animals": VariantSpec(
        "Rotate the animal to face the same direction as the hand. Use the fewest clicks.",
        rotate=True,
    ),
    "3d_rollball_animals_multi": VariantSpec(
        "Rotate the animal to face the same direction as the hand. Use the fewest clicks.",
        rotate=True,
    ),
    "3d_rollball_objects": VariantSpec(
        "Use the arrows to rotate the object to face in the direction of the hand.",
        rotate=True,
    ),
    "3d_rollball_objects_v2": VariantSpec(
        "Use the arrows to rotate the object to face in the direction of the hand.",
        rotate=True,
    ),
    "3d_rollball_objects_v3": VariantSpec(
        "Use the arrows to rotate the object to face in the direction of the hand.",
        rotate=True,
    ),
    "3drollball_v2_var1": VariantSpec(
        "Rotate the object to face the same direction as the hand. Use the fewest clicks.",
        rotate=True,
    ),
    "3drollball_v2_var2": VariantSpec(
        "Rotate the object to face the same direction as the hand. Use the fewest clicks.",
        rotate=True,
    ),
    "darts_matchkey": VariantSpec("Pick the image where the darts add up to the number shown.", 2, 3),
    "diceico": VariantSpec(
        "Match the icons on the left with the icons on the top faces of the dice.", 1, 8
    ),
    "dicematch": VariantSpec(
        "Match the icons on the left with the icons on the top faces of the dice.", 1, 6
    ),
    "dice_pair": VariantSpec(
        "Match the icons on the left with the icons on the top faces of the dice.", 1, 6
    ),
    "icongrouping": VariantSpec("Pick the image where the icons are grouped the same way as the example.", 1, 6),
    "icon_connect": VariantSpec("Pick the image that continues the icon connections.", 1, 6),
    "cardistance": VariantSpec(
        "Use the arrows to find the distance between the two cars that matches the left image.",
        rotate=True,
    ),
    "coordinatesmatch": VariantSpec(
        "Using the arrows, move the person to the indicated seat.",
        rotate=True,
    ),
    "penguins": VariantSpec("Pick the penguin.", 1, 6),
    "rockstack": VariantSpec(
        "Using the arrows, pick the group of rocks that has the amount indicated on the left.",
        rotate=True,
    ),
}


def lookup_variant(instruction: str) -> VariantSpec:
    v = norm_variant(instruction)
    if not v:
        return VariantSpec()
    if v in _VARIANT_TABLE:
        return _VARIANT_TABLE[v]
    if "diceico" in v:
        return _VARIANT_TABLE["diceico"]
    if "dicematch" in v or "dice_pair" in v or "dice" in v:
        return _VARIANT_TABLE["dicematch"]
    if "hopscotch_highsec" in v:
        return _VARIANT_TABLE["hopscotch_highsec"]
    if "hopscotch" in v:
        return _VARIANT_TABLE["hopscotchv2"]
    if "rollball" in v:
        return _VARIANT_TABLE["3d_rollball_animals"]
    if "conveyor" in v:
        return _VARIANT_TABLE["conveyor_belt_v2"]
    if "penguin" in v:
        return _VARIANT_TABLE["penguins"]
    if "coordinatesmatch" in v:
        return _VARIANT_TABLE["coordinatesmatch"]
    if "cardistance" in v:
        return _VARIANT_TABLE["cardistance"]
    if "rockstack" in v:
        return _VARIANT_TABLE["rockstack"]
    if "darts" in v:
        return _VARIANT_TABLE["darts_matchkey"]
    return VariantSpec()


def spec_for_game(instruction: str, game_variant: str) -> VariantSpec:
    spec = lookup_variant(instruction)
    alt = lookup_variant(game_variant)
    if alt.rotate:
        spec.rotate = True
        if spec.comment == FALLBACK_COMMENT:
            spec.comment = alt.comment
    elif spec.comment == FALLBACK_COMMENT and alt.comment != FALLBACK_COMMENT:
        spec = alt
    human = (instruction or "").strip()
    if " " in human and is_mostly_english(human):
        spec.comment = human
    if not spec.comment:
        spec.comment = FALLBACK_COMMENT
    return spec


_seed_official()
