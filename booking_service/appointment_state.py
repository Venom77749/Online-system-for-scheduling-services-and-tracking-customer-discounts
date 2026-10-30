from abc import ABC, abstractmethod


class AppointmentLifecycle:
    def __init__(self, appointment_id: str, on_completed_callback=None):
        self.appointment_id = appointment_id
        self._callback = on_completed_callback
        self.state: "IAppointmentState" = CreatedState()

    def set_state(self, state: "IAppointmentState"):
        print(f"[Booking / State] Запись {self.appointment_id}: {self.state.__class__.__name__} -> {state.__class__.__name__}")
        self.state = state

    def confirm(self):
        self.state.confirm(self)

    def complete(self):
        self.state.complete(self)
        if self._callback:
            self._callback(self.appointment_id)

    def cancel(self):
        self.state.cancel(self)


class IAppointmentState(ABC):
    @abstractmethod
    def confirm(self, ctx: AppointmentLifecycle): ...
    @abstractmethod
    def complete(self, ctx: AppointmentLifecycle): ...
    @abstractmethod
    def cancel(self, ctx: AppointmentLifecycle): ...


class CreatedState(IAppointmentState):
    def confirm(self, ctx: AppointmentLifecycle):
        ctx.set_state(ConfirmedState())

    def complete(self, ctx: AppointmentLifecycle):
        raise ValueError("Нельзя завершить неподтвержденную запись")

    def cancel(self, ctx: AppointmentLifecycle):
        ctx.set_state(CancelledState())


class ConfirmedState(IAppointmentState):
    def confirm(self, ctx: AppointmentLifecycle):
        pass

    def complete(self, ctx: AppointmentLifecycle):
        ctx.set_state(CompletedState())

    def cancel(self, ctx: AppointmentLifecycle):
        ctx.set_state(CancelledState())


class CompletedState(IAppointmentState):
    def confirm(self, ctx: AppointmentLifecycle):
        raise ValueError("Услуга уже выполнена")

    def complete(self, ctx: AppointmentLifecycle):
        pass

    def cancel(self, ctx: AppointmentLifecycle):
        raise ValueError("Нельзя отменить выполненную запись")


class CancelledState(IAppointmentState):
    def confirm(self, ctx: AppointmentLifecycle):
        raise ValueError("Нельзя подтвердить отмененную запись")

    def complete(self, ctx: AppointmentLifecycle):
        raise ValueError("Нельзя завершить отмененную запись")

    def cancel(self, ctx: AppointmentLifecycle):
        pass