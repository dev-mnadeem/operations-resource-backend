from apps.inventory.models import BranchInventory


class ReplenishmentAdvice(BranchInventory):
    """
    A proxy over BranchInventory that exists purely to give replenishment its
    own admin screen.

    No new table and no migration of substance: the underlying rows are the
    same stock records, presented with the derived figures a buyer needs
    (days of cover, reorder point, suggested order) rather than the raw
    quantity the stock screen shows.
    """

    class Meta:
        proxy = True
        verbose_name = "Replenishment advice"
        verbose_name_plural = "Replenishment advice"
