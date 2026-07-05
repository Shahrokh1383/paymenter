from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.identity.domain.entities.user import User
from src.identity.domain.value_objects.phone_email import PhoneEmail
from src.identity.domain.repositories import UserRepository
from src.identity.domain.events.user_events import UserRegisteredEvent
from src.identity.application.commands.register_user_command import RegisterUserCommand
from src.common.domain.exceptions import UserAlreadyExistsError

class RegisterUserHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        user_repo: UserRepository,
        event_bus: EventBus
    ):
        self._uow = uow
        self._user_repo = user_repo
        self._event_bus = event_bus

    def handle(self, command: RegisterUserCommand) -> int:
        # 1. Validate phone_email with Value Object
        phone_email_vo = PhoneEmail(command.phone_email)

        with self._uow:
            # 2. Check uniqueness (domain invariant)
            if self._user_repo.exists_by_phone_email(str(phone_email_vo)):
                raise UserAlreadyExistsError(f"User with {phone_email_vo} already exists.")

            # 3. Create transient user (id=None)
            user = User(id=None, name=command.name.strip(), phone_email=phone_email_vo)
            user_id = self._user_repo.add(user)

            self._uow.commit()
            self._event_bus.publish(UserRegisteredEvent(
                user_id=user_id,
                name=user.name,
                phone_email=user.phone_email
            ))
        return user_id