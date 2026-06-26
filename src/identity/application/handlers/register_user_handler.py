from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.entities.user import User
from src.identity.domain.repositories import UserRepository
from src.identity.domain.ports.account_provisioning_port import AccountProvisioningPort
from src.identity.application.commands.register_user_command import RegisterUserCommand

class RegisterUserHandler:
    def __init__(self, uow: UnitOfWork, user_repo: UserRepository, account_port: AccountProvisioningPort):
        self._uow = uow
        self._user_repo = user_repo
        self._account_port = account_port

    def handle(self, command: RegisterUserCommand) -> None:
        with self._uow:
            user = User(id=0, name=command.name, phone_email=command.phone_email)
            user_id = self._user_repo.add(user)
            # Delegate account creation to Ledger via ACL
            self._account_port.create_default_account(user_id=user_id, currency_id=1)
            self._uow.commit()