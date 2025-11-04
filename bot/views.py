
import discord
from discord.ui import View, Button
from persistence.repository import Repository

class VoteButton(Button):
    def __init__(self, repository: Repository, round_id: int, index: int, label: str):
        super().__init__(style=discord.ButtonStyle.primary, label=f"{index}. {label}", custom_id=f"vote:{round_id}:{index}")
        self.repository = repository
        self.round_id = round_id
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        votes = await self.repository.load_votes()
        r = next((x for x in votes if x.get("id") == self.round_id), None)
        if not r or r.get("status") != "open":
            await interaction.response.send_message("This vote is closed.", ephemeral=True)
            return
        user_id = str(interaction.user.id)
        r.setdefault("ballots", {})
        r["ballots"][user_id] = self.index
        await self.repository.save_votes(votes)
        await interaction.response.defer()

class VoteView(View):
    def __init__(self, repository: Repository, round_id: int, options: list[dict]):
        super().__init__(timeout=None)
        for opt in options:
            self.add_item(VoteButton(repository, round_id, opt["index"], opt["label"]))
