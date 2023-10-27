import ast
import os
import random
import re
import aiohttp
import openai
import pandas as pd
import tiktoken
import json

from interactions import (
    Extension,
    slash_command,
    SlashContext,
    listen,
    check,
    has_role,
    message_context_menu,
    ContextMenuContext,
    Modal,
    ParagraphText,
    MemberFlags,
)
from interactions.api.events import MessageCreate, MemberUpdate, MemberAdd
from interactions.ext.paginators import Paginator
from scipy import spatial

EMBERWIND_KEY = os.getenv("EMBERWIND_KEY")
EMBERWIND_EMAIL = os.getenv("EMBERWIND_EMAIL")
EMBERWIND_PASSWORD = os.getenv("EMBERWIND_PASSWORD")
openai.api_key = os.getenv("OPENAI_KEY")
openai.organization = os.getenv("OPENAI_ORG")

SETUP_MESSAGE: dict[str, str] = {
    "role": "system",
    "content": "You are Momnisaur, the mother of the Nomnisaurs. You will act like a mother while providing helpful "
    "and informative replies. Be sure to speak as Momnisaur in first person. Nomnisaurs appear in two "
    "games, Snack Attack and Dungeons and Dinos. Nomnisaurs love eating everything they can, and "
    "especially love sweet and spicy flavors. They hate bitter and sour flavors. In Dungeons and Dinos, "
    "there are 6 Nomnisaurs shown, Nom Chompsky the Wizard, Juicebox the Healer, Meatball the Fighter, "
    "Gabu the Rogue, Al the Bard, and Dente the Dancer.",
}

DADDISAUR_MESSAGE: dict[str, str] = {
    "role": "system",
    "content": "You are Daddisaur, the father of the Nomnisaurs. You will act like a father while providing cheesy "
    "dad jokes. Be sure to speak as Daddisaur in third person. Nomnisaurs appear in two "
    "games, Snack Attack and Dungeons and Dinos. Nomnisaurs love eating everything they can, and "
    "especially love sweet and spicy flavors. They hate bitter and sour flavors. In Dungeons and Dinos, "
    "there are 6 Nomnisaurs shown, Nom Chompsky the Wizard, Juicebox the Healer, Meatball the Fighter, "
    "Gabu the Rogue, Al the Bard, and Dente the Dancer.",
}

FUNNY_WORDS: list[str] = [
    "brain",
    "cabbage",
    "candy",
    "chicken",
    "chocolate",
    "cookie",
    "dinosaur",
    "dino",
    "cow",
    "hands",
    "atoms",
    "molecules",
    "sugar",
    "spice",
    "everything",
    "nothing",
    "food",
    "snack",
    "breakfast",
    "lunch",
    "dinner",
    "dessert",
    "sweets",
    "sour",
    "bitter",
    "dice",
    "d20",
    "d12",
    "d10",
    "d8",
    "d6",
    "d4",
    "d100",
    "mice",
    "cheese",
    "milk",
    "eggs",
    "bees",
]

CLEAN_HTML: re.Pattern = re.compile(r"<.*?>")

DATA_PATH: str = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "data"))
print(DATA_PATH)

SAVE_PATHS: dict[str, str] = {
    "faq": f"{DATA_PATH}\\faq.csv",
    "rules": f"{DATA_PATH}\\rules.csv",
    "corrections": f"{DATA_PATH}\\corrections.csv",
    "actions": f"{DATA_PATH}\\actions.csv",
}

CHAT_MODEL: str = "gpt-3.5-turbo"
EMBEDDING_MODEL: str = "text-embedding-ada-002"

SCOPES = [518833007398748161, 1041764477714051103]

CLEAN_NAME: re.Pattern = re.compile(r"[\W_]+")


class AI(Extension):
    def __init__(self, bot):
        self.new_members = []
        self.update_rules_df()

    @staticmethod
    def num_tokens(text: str, model: str = CHAT_MODEL) -> int:
        """Return the number of tokens in a string."""
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))

    @staticmethod
    async def strings_ranked_by_relatedness(
        query: str,
        df: pd.DataFrame,
        relatedness_fn=lambda x, y: 1 - spatial.distance.cosine(x, y),
        top_n: int = 100,
    ) -> tuple[list[str], list[float]]:
        """Returns a list of strings and relatednesses, sorted from most related to least."""
        query_embedding_response = await openai.Embedding.acreate(
            model=EMBEDDING_MODEL,
            input=query,
        )
        query_embedding = query_embedding_response["data"][0]["embedding"]
        strings_and_relatednesses = [
            (row["text"], relatedness_fn(query_embedding, row["embedding"]))
            for i, row in df.iterrows()
        ]
        strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)
        strings, relatednesses = zip(*strings_and_relatednesses)
        return strings[:top_n], relatednesses[:top_n]

    @staticmethod
    async def query_message(
        query: str,
        df: pd.DataFrame,
        model: str,
        token_budget: int,
        custom_introduction: str = "",
    ) -> str:
        """Return a message for GPT, with relevant source texts pulled from a dataframe."""
        strings, relatednesses = await AI.strings_ranked_by_relatedness(
            query, df, top_n=6
        )
        if custom_introduction:
            introduction = custom_introduction
        else:
            introduction = (
                "Use the below text about Emberwind to answer the subsequent question. Make sure to also "
                "give the reasoning behind the answer to the best of your ability. If the answer cannot be"
                ' found in the text, write "I could not find an answer."\n\nEmberwind rules section:\n"""'
            )
        question = f"\n\nQuestion: {query}"
        message = introduction
        for string in strings:
            next_article = "\n" + string + "\n"
            if (
                AI.num_tokens(message + next_article + question, model=model)
                > token_budget
            ):
                break
            else:
                message += next_article
        return message + '"""\n\n' + question

    @listen()
    async def on_member_add(self, event: MemberAdd):
        self.new_members.append(event.member)

    @listen()
    async def on_member_update(self, event: MemberUpdate):
        if (
            MemberFlags.COMPLETED_ONBOARDING not in event.before.flags
            and MemberFlags.COMPLETED_ONBOARDING in event.after.flags
            and event.after in self.new_members
        ):
            print("Member Completed Onboarding")
            response = await openai.ChatCompletion.acreate(
                model=CHAT_MODEL,
                messages=[
                    SETUP_MESSAGE,
                    {
                        "role": "user",
                        "content": f"Welcome {event.after.mention} to the ***EMBERWIND*** discord server!"
                        f" Make sure to say their name. Mention that you can be pinged for ***EMBERWIND*** rules"
                        f" questions in {self.bot.get_channel(518833140807237653).mention}.",
                    },
                ],
            )
            self.new_members.remove(event.after)
            introduction_channel = await self.bot.fetch_channel(518834266109509632)
            await introduction_channel.send(response.choices[0].message.content)

    @listen()
    async def on_message_create(self, event: MessageCreate):
        if "<@983043389425610873>" in event.message.content:
            print("Processing Request")

            if "sync-commands" in event.message.content:
                await event.message.reply("Syncing Commands")
                await self.bot.synchronise_interactions(scopes=SCOPES)
                return

            reply_to = event.message
            replied_message = event.message.get_referenced_message()
            content = event.message.content.replace("<@983043389425610873>", "").strip()

            is_rules_search = False
            if "rules-search" in event.message.content:
                content = content.replace("rules-search", "").strip()
                is_rules_search = True

            is_forcing_dad = False
            if "force-dad" in event.message.content:
                content = content.replace("force-dad", "").strip()
                is_forcing_dad = True

            if not content and replied_message:
                content = replied_message.content
                reply_to = replied_message
            elif replied_message:
                content += "\n\nIn Reply To:\n" + replied_message.content

            edit_when_done = await reply_to.reply("Thinking...")

            if is_rules_search or event.message.channel == self.bot.get_channel(
                518833140807237653
            ):
                message = await AI.query_message(
                    content, self.bot.rules_df, model=CHAT_MODEL, token_budget=1024
                )
                print(message)
                rules_messages = [
                    {
                        "role": "system",
                        "content": "You are Momnisaur, the mother of the Nomnisaurs. You will act like a "
                        "mother while providing helpful and informative replies. Be sure to"
                        " speak as Momnisaur in first person. Speak about Emberwind as if you "
                        "were part of the team that made the rules.",
                    },
                    {"role": "user", "content": message},
                ]

                response = await openai.ChatCompletion.acreate(
                    model=CHAT_MODEL,
                    messages=rules_messages,
                    temperature=0.5,
                )

            else:
                history = []

                channel = event.message.channel
                channel_history = await channel.history(
                    limit=20, before=event.message.id
                ).fetch()
                for message in channel_history:
                    if AI.num_tokens("\n".join([x for x in history])) > 500:
                        break

                    text = (
                        message.content.replace(self.bot.user.mention, "")
                        .replace("rules-search", "")
                        .strip()
                    )
                    if not text:
                        continue

                    clean_name = CLEAN_NAME.sub("", message.author.display_name)
                    history.append(
                        f"{clean_name + ': ' if message.author != self.bot.user else ''}{text}"
                    )

                history.reverse()
                history_str = "\n".join(history)
                clean_name = CLEAN_NAME.sub("", reply_to.author.display_name)
                full_context = (
                    f"Use the following chat history as context when replying to this message from"
                    f' {clean_name}.\n\nChat History:\n"""\n{history_str}""\'\n\nMessage from'
                    f" {clean_name}: {content}"
                )

                introduction = (
                    "The below text is are any relevant Emberwind rules if you think the question is "
                    'about Emberwind. If it is not Emberwind related, answer normally.\n\nEmberwind rules section:\n"""'
                )

                message = await AI.query_message(
                    content,
                    self.bot.rules_df,
                    model=CHAT_MODEL,
                    token_budget=512,
                    custom_introduction=introduction,
                )
                message = message.replace(f"\n\nQuestion: {content}", "")

                full_prompt = f"{message}\n\n{full_context}"
                print(full_prompt)
                messages = [
                    SETUP_MESSAGE,
                    {"role": "user", "content": full_prompt},
                ]
                response = await openai.ChatCompletion.acreate(
                    model=CHAT_MODEL,
                    messages=messages,
                )

            reply = response.choices[0].message.content

            reply = await self.format_text(reply)

            if is_forcing_dad or random.randint(1, 69) == 69:
                reply = reply[: len(reply) // 2] + "-\n\n" + await AI.get_dad_joke()

            if len(reply) > 1900:
                paginator = Paginator.create_from_string(
                    self.bot, reply, page_size=1900
                )
                paginator._author_id = reply_to.author
                await edit_when_done.edit(**paginator.to_dict(), content="")
            else:
                await edit_when_done.edit(content=reply)

    async def format_text(self, text):
        toughness_icon = await self.bot.fetch_custom_emoji(
            755894720546471947, 518833007398748161
        )
        resistance_icon = await self.bot.fetch_custom_emoji(
            755894720927891557, 518833007398748161
        )
        dodge_icon = await self.bot.fetch_custom_emoji(
            755894720588415087, 518833007398748161
        )
        willpower_icon = await self.bot.fetch_custom_emoji(
            755894720932216945, 518833007398748161
        )
        # define desired replacements here
        rep = {
            "fallen": "***FALLEN***",
            "auto-hit": "***AUTO-HIT***",
            "auto-crit": "***AUTO-CRIT***",
            "piercing": "***PIERCING***",
            "burning": "***BURNING***",
            "chilled": "***CHILLED***",
            "chill": "***CHILL***",
            "dazed": "***DAZED***",
            "daze": "***DAZE***",
            "fragility": "***FRAGILITY***",
            "off-guard": "***OFF-GUARD***",
            "poisoned": "***POISONED***",
            "poison": "***POISON***",
            "prone": "***PRONE***",
            "paralyzed": "***PARALYZED***",
            "paralysis": "***PARALYSIS***",
            "silenced": "***SILENCED***",
            "silence": "***SILENCE***",
            "sleeping": "***SLEEPING***",
            "sleep": "***SLEEP***",
            "weakness": "***WEAKNESS***",
            "vulnerability": "***VULNERABILITY***",
            "vs": "***VS***",
            "toughness": f"**Toughness** {toughness_icon}",
            "resistance": f"**Resistance** {resistance_icon}",
            "dodge": f"**Dodge** {dodge_icon}",
            "willpower": f"**Willpower** {willpower_icon}",
            "critical": "**Critical (C)**",
            "accuracy": "**Accuracy (A)**",
            "penetration": "**Penetration (P)**",
            "cap check": "**CAP Check**",
            " cap": " **CAP**",
            " dm": " Storyteller",
        }
        extended_rep = {}
        for key, value in rep.items():
            extended_rep[key.title()] = value
            extended_rep[key.upper()] = value
        rep.update(extended_rep)
        # use these three lines to do the replacement
        rep = dict((re.escape(k), v) for k, v in rep.items())
        pattern = re.compile("|".join(rep.keys()))
        pattern2 = re.compile(r"\*{4,}")
        text = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
        text = pattern2.sub("***", text)
        return text

    def update_rules_df(self):
        self.bot.rules_df = pd.concat(
            (pd.read_csv(path) for path in SAVE_PATHS.values() if os.path.isfile(path)),
            ignore_index=True,
        )
        self.bot.rules_df["embedding"] = self.bot.rules_df["embedding"].apply(
            ast.literal_eval
        )

    @staticmethod
    def update_command(name, description=""):
        def wrapper(func):
            return slash_command(
                name="update",
                description="Updates one of the Momnisaur's data files.",
                sub_cmd_name=name,
                sub_cmd_description=description,
                scopes=SCOPES,
            )(func)

        return wrapper

    @update_command(name="knowledge_base")
    @check(has_role(525501383189856278))
    async def get_knowledge_base(self, ctx: SlashContext):
        await ctx.send("Updating Knowledge Base Embeddings")

        headers = {"Emberwind-Api-Key": EMBERWIND_KEY}
        params = {
            "page": 0,
            "size": 1000,
        }

        data = []

        async with aiohttp.ClientSession(headers=headers) as session:
            url = "https://emberwindgame.com/emberwind-web/api/v1/web/content/faq"
            async with session.get(url, params=params) as resp:
                result = await resp.json()
                for faq in result["data"]:
                    async with session.get(f"{url}/{faq['slug']}") as faq_resp:
                        question = await faq_resp.json()
                        formatted = (
                            f"{' '.join(x['name'] for x in question['path'])}\n"
                            f"{question['question']}\n"
                            f"{question['answer']}"
                        )
                        formatted = re.sub(CLEAN_HTML, " ", formatted)
                        data.append(
                            formatted.replace("#", "")
                            .replace("@", "")
                            .replace("$", "")
                            .strip()
                        )

        embeddings = await self.get_embeddings_from_data(data)

        df = pd.DataFrame({"text": data, "embedding": embeddings})
        df.to_csv(SAVE_PATHS["faq"], index=False)
        self.update_rules_df()

        await ctx.send("Finished Updating Local Knowledge Base")

    @update_command(name="comprehensive_rules")
    @check(has_role(525501383189856278))
    async def update_rules(self, ctx: SlashContext):
        await ctx.send("Updating Comprehensive Rules Embeddings")

        with open(f"{DATA_PATH}\\RAWRules.txt", "r", encoding="utf8") as rules:
            rules_text = rules.read()
            data = [rule.strip() for rule in rules_text.split(";/.")]

        embeddings = await self.get_embeddings_from_data(data)

        df = pd.DataFrame({"text": data, "embedding": embeddings})
        df.to_csv(f"{DATA_PATH}\\rules.csv", index=False)
        self.update_rules_df()

        await ctx.send("Finished Updating Local Comprehensive Rules")

    @update_command(name="hero_actions")
    @check(has_role(525501383189856278))
    async def get_hero_actions(self, ctx: SlashContext):
        await ctx.send("Updating Hero Actions Embeddings")

        headers = {"Emberwind-Api-Key": EMBERWIND_KEY}

        data = []
        classes = [
            "archer",
            "ardent",
            "atlanta",
            "druid",
            "invoker",
            "rogue",
            "spiritualist",
            "tactician",
            "warrior",
        ]

        subclasses = [
            "elysian_legionnaire",
            "hekau",
            "nightshade",
            "saviour",
            "wildfang",
        ]

        async with aiohttp.ClientSession(headers=headers) as session:
            auth_url = "https://emberwindgame.com/emberwind-web/api/v1/web/auth/login"
            body = json.dumps(
                {
                    "email": EMBERWIND_EMAIL,
                    "password": EMBERWIND_PASSWORD,
                    "rememberMe": False,
                }
            )

            async with session.post(
                auth_url,
                data=body,
                headers={"Content-Type": "application/json", "Accept": "*/*"},
            ) as resp:
                if resp.status != 200:
                    await ctx.send("Failed to login to Emberwind")
                    return

            for hero_class in classes:
                url = (
                    f"https://emberwindgame.com/emberwind-web/api/v1/web/heroes/hero-creator/classes/"
                    f"{hero_class}/options/up-to-tier/4"
                )
                async with session.get(url) as resp:
                    result = await resp.json()
                    for tier in result:
                        for action, category in [
                            *[(t, "Trait") for t in tier["traits"]],
                            *[(a, "Class Action") for a in tier["actions"]],
                            *[
                                (t, "Tide Turner Action")
                                for t in tier["tideTurnerActions"]
                            ],
                        ]:
                            name = action.get("name", "")
                            type = action.get("type", "")
                            subtype = action.get("subtype", "")
                            target = action.get("target", "")
                            range_description = action.get("rangeDescription", "")
                            action_range = action.get("range", "")
                            action_speed = action.get("actionSpeed", "")
                            effect = action.get("effect", "")

                            formatted = f"Class: {hero_class.capitalize()}\n"
                            formatted += f"{category}: {name}\n"
                            if type == "Passive":
                                formatted += f"Type: {type}\n"
                            else:
                                formatted += f"Type: {type} / {subtype}\n"
                                formatted += f"Target: {target}\n"
                                if action_range:
                                    formatted += (
                                        f"Range: {range_description} / {action_range}\n"
                                    )
                                formatted += f"Speed: {action_speed}\n"
                            formatted += f"Effect: {effect}"

                            formatted = re.sub(CLEAN_HTML, " ", formatted)
                            data.append(
                                formatted.replace("#", "")
                                .replace("@", "")
                                .replace("$", "")
                                .strip()
                            )

            for subclass in subclasses:
                url = (
                    f"https://emberwindgame.com/emberwind-web/api/v1/web/heroes/hero-creator/subclasses/"
                    f"{subclass}/options/up-to-tier/4"
                )
                async with session.get(url) as resp:
                    result = await resp.json()
                    for tier in result:
                        for action, category in [
                            *[(t, "Trait") for t in tier["traits"]],
                            *[(a, "Class Action") for a in tier["actions"]],
                            *[
                                (t, "Tide Turner Action")
                                for t in tier["tideTurnerActions"]
                            ],
                        ]:
                            name = action.get("name", "")
                            type = action.get("type", "")
                            subtype = action.get("subtype", "")
                            target = action.get("target", "")
                            range_description = action.get("rangeDescription", "")
                            action_range = action.get("range", "")
                            action_speed = action.get("actionSpeed", "")
                            effect = action.get("effect", "")

                            formatted = f"Class: {subclass.capitalize()}\n"
                            formatted += f"{category}: {name}\n"
                            if type == "Passive":
                                formatted += f"Type: {type}\n"
                            else:
                                formatted += f"Type: {type} / {subtype}\n"
                                formatted += f"Target: {target}\n"
                                if action_range:
                                    formatted += (
                                        f"Range: {range_description} / {action_range}\n"
                                    )
                                formatted += f"Speed: {action_speed}\n"
                            formatted += f"Effect: {effect}"

                            formatted = re.sub(CLEAN_HTML, " ", formatted)
                            data.append(
                                formatted.replace("#", "")
                                .replace("@", "")
                                .replace("$", "")
                                .strip()
                            )

        embeddings = await self.get_embeddings_from_data(data)

        df = pd.DataFrame({"text": data, "embedding": embeddings})
        df.to_csv(SAVE_PATHS["actions"], index=False)
        self.update_rules_df()

        await ctx.send("Finished Updating Local Hero Actions")

    async def get_embeddings_from_data(self, data):
        batch_size = 1000
        embeddings = []
        for batch_start in range(0, len(data), batch_size):
            batch_end = batch_start + batch_size
            batch = data[batch_start:batch_end]
            print(f"Batch {batch_start} to {batch_end - 1}")
            response = await openai.Embedding.acreate(
                model=EMBEDDING_MODEL, input=batch
            )
            for i, be in enumerate(response["data"]):
                assert i == be["index"]
            batch_embeddings = [e["embedding"] for e in response["data"]]
            embeddings.extend(batch_embeddings)
        return embeddings

    async def update_corrections(self):
        with open(
            f"{DATA_PATH}\\corrections.txt", "r", encoding="utf8"
        ) as corrections_file:
            corrections_text = corrections_file.read().strip().strip(";/.")
            data = [correction.strip() for correction in corrections_text.split(";/.")]

        embeddings = await self.get_embeddings_from_data(data)

        df = pd.DataFrame({"text": data, "embedding": embeddings})
        df.to_csv(f"{DATA_PATH}\\corrections.csv", index=False)
        self.update_rules_df()

    @message_context_menu(
        name="Correct",
        scopes=SCOPES,
    )
    @check(has_role(525501383189856278))
    async def correct(self, ctx: ContextMenuContext):
        if ctx.target.author.id != self.bot.user.id:
            await ctx.send("I can only correct my own messages.", ephemeral=True)
            return

        print("Correcting")

        reply_to = await ctx.channel.fetch_message(
            ctx.target.message_reference.message_id
        )
        question = reply_to.content
        question = (
            question.replace(self.bot.user.mention, "")
            .replace("rules-search", "")
            .strip()
        )

        modal = Modal(
            ParagraphText(
                label="What is the correct answer?",
                custom_id="correct_answer",
            ),
            title="Correct Answer",
        )
        await ctx.send_modal(modal=modal)
        modal_ctx = await self.bot.wait_for_modal(modal)
        await modal_ctx.defer(ephemeral=True)

        response = await openai.ChatCompletion.acreate(
            model=CHAT_MODEL,
            messages=[
                SETUP_MESSAGE,
                {"role": "user", "content": question},
                {"role": "assistant", "content": ctx.target.content},
                {
                    "role": "user",
                    "content": f"State that you were wrong and the correct answer is: "
                    f"{modal_ctx.responses['correct_answer']}. "
                    f"Respond as if you were correcting yourself.",
                },
            ],
        )

        reply = await self.format_text(response.choices[0].message.content)
        await reply_to.reply(reply)
        await modal_ctx.send("Corrected")

        with open(f"{DATA_PATH}\\corrections.txt", "a+") as file:
            file.write(f"{question}\n{modal_ctx.responses['correct_answer']}\n;/.\n")

        await self.update_corrections()

    @slash_command(name="dad_joke", scopes=SCOPES, description="Get a random dad joke")
    async def dad_joke(self, ctx: SlashContext):
        await ctx.defer()
        joke = await AI.get_dad_joke()
        await ctx.send(joke)

    @staticmethod
    async def get_dad_joke():
        response = await openai.ChatCompletion.acreate(
            model=CHAT_MODEL,
            messages=[
                DADDISAUR_MESSAGE,
                {
                    "role": "user",
                    "content": f"Tell me a dad joke about {random.choice(FUNNY_WORDS)}. Wrap the joke "
                    f"in quotation marks. Prefix the joke with a note in italics about "
                    f"Daddisaur chiming in from another room or entering the room and "
                    f"leaving after. Use proper grammar and punctuation.",
                },
            ],
        )
        print(response.choices[0].message.content)
        return response.choices[0].message.content


def setup(bot):
    AI(bot)
