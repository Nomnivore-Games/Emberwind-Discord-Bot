import dice

from interactions import Extension, slash_command, SlashContext, slash_option, OptionType

SCOPES = [518833007398748161, 1041764477714051103]


class Dice(Extension):
    def __init__(self, bot):
        pass

    @slash_command(
        name="roll",
        description="Rolls the dice",
        scopes=SCOPES
    )
    @slash_option(
        name="dice",
        description="The dice to roll",
        opt_type=OptionType.STRING,
        required=True,
        argument_name="dice_roll"
    )
    async def roll(self, ctx: SlashContext, dice_roll: str):
        await ctx.defer()
        result: dice.elements.Element = dice.roll(dice_roll)
        if type(result) == dice.elements.Roll:
            result = sum(result)
        await ctx.send(f"{dice_roll} -> {result}")


def setup(bot):
    Dice(bot)
